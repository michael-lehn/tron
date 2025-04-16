import collections
import select
import socket
import sys
import time

from enum import Enum, auto

FPS = 40
HOST = '0.0.0.0'
PORT = 65432

WIDTH = 1000
HEIGHT = 1000
NUM_PLAYERS = 3

SPEED = (0.1, 0.3, 0.7, 0.9, 1.0, 1.1, 1.3, 1.7, 2.5, 4.1)
SPEED_INITIAL = 4

class TronServerConnection:
    def __init__(self, host, port, num_players):
        self.HOST = host
        self.PORT = port

        self.num_players = num_players
        self.conn = [None] * self.num_players
        self.name = [None] * self.num_players
        self.buff = [""] * self.num_players
        self.line = [None] * self.num_players

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.bind((self.HOST, self.PORT))
            self.sock.listen(2 * self.num_players)

            print(f"TRON server running on {self.HOST}:{self.PORT}")
            print(f"Waiting for {self.num_players} players...")
            return True
        except OSError as e:
            print(f"Could not start server on {self.HOST}:{self.PORT}")
            print(f"Error: {type(e).__name__} – {e}")
            return False

    def num_joined(self):
        return sum(x is not None for x in self.name)

    def disconnect_player(self, player_index):
        self.conn[player_index] = None
        self.name[player_index] = None
        self.buff[player_index] = ""
        self.line[player_index] = None

    def accept_new_connection(self):
        try:
            free_index = self.conn.index(None)
        except ValueError:
            return -1

        try:
            readable, _, _ = select.select([self.sock], [], [], 0)
            if self.sock in readable:
                conn, addr = self.sock.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn.setblocking(False)

                self.conn[free_index] = conn
                print(f"New connection from {addr} assigned to slot "
                      f"{free_index}")
                return free_index
        except Exception as e:
            print(f"Error accepting connection: {type(e).__name__} – {e}")

        return -1

    def is_connection_alive(self, player_index):
        conn = self.conn[player_index]
        if conn is None:
            return False
        try:
            readable, _, _ = select.select([conn], [], [], 0)
            if conn in readable:
                data = conn.recv(1, socket.MSG_PEEK)
                if data == b"":  # sauber geschlossen
                    return False
        except (BlockingIOError, ConnectionResetError, BrokenPipeError,
                OSError):
            return False
        return True

    def update_connections(self):
        for i, conn in enumerate(self.conn):
            if conn is not None and not self.is_connection_alive(i):
                print(f"Player {i + 1} disconnected (connection dead)")
                self.disconnect_player(i)

    def send_to_client(self, i, msg):
        conn = self.conn[i]
        if conn is None:
            return False
        try:
            conn.sendall(msg.encode("utf-8"))
            return True
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"Send error to Player {i + 1}: {type(e).__name__} – {e}")
            self.disconnect_player(i)
            return False

    def broadcast(self, msg, newline = True):
        begin = "" if newline else "\r"
        end = "\n" if newline else ""
        print(f"{begin}Broadcast: {msg.strip()}", end=end)
            
        for i in range(len(self.conn)):
            if self.conn[i] is not None:
                if not self.send_to_client(i, msg):
                    print(f"Could not send to Player {i + 1}")

    def read_from_client(self, player_index):
        conn = self.conn[player_index]
        if conn is None:
            return False

        try:
            readable, _, _ = select.select([conn], [], [], 0)
            if conn in readable:
                data = conn.recv(64)
                if not data:
                    print(f"Player {player_index + 1} disconnected "
                          f"(recv returned empty)")
                    self.disconnect_player(player_index)
                    return False
                self.buff[player_index] += data.decode("utf-8")
                return True
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"Error reading from Player {player_index + 1}: "
                  f"{type(e).__name__} – {e}")
            self.disconnect_player(player_index)
            return False
        return False

    def getchar_from_client(self, player_index):
        if self.conn[player_index] is None:
            return ""
        self.read_from_client(player_index)

        if len(self.buff[player_index]) > 0:
            ch = self.buff[player_index][0]
            self.buff[player_index] = self.buff[player_index][1:]
            return ch
        return ""

    def readline_from_client(self, player_index):
        if self.conn[player_index] is None:
            return ""
        self.read_from_client(player_index)
        
        if "\n" in self.buff[player_index]:
            line, self.buff[player_index] \
                    = self.buff[player_index].split("\n", 1)
            return line.strip()

        return ""


class TronServer:

    class State(Enum):
        ERR = auto()                        # can not connect
        INITIAL = auto()
        WAITING_FOR_PLAYERS = auto()
        ALL_PLAYERS_CONNECTED = auto()
        WAITING_FOR_GO = auto()
        GAME_STARTED = auto()
        WAITING_FOR_END = auto()

    def __init__(self, host, port, width, height, num_players):
        assert num_players <= 4

        self.host = host
        self.port = port
        self.width = width
        self.height = height
        self.num_players = num_players
        self.ready_to_go = None
        self.confirmed_end = None

        self.arena = None
        self.player = [None] * self.num_players
        self.dt = 0

        self.state = TronServer.State.INITIAL
        self.last_state = None

        self.conn = None        # set by handle_initial

        self.state_handlers = {
            TronServer.State.ERR:
                self.handle_err,
            TronServer.State.INITIAL:
                self.handle_initial,
            TronServer.State.WAITING_FOR_PLAYERS:
                self.handle_waiting_for_players,
            TronServer.State.ALL_PLAYERS_CONNECTED:
                self.handle_all_players_connected,
            TronServer.State.WAITING_FOR_GO:
                self.handle_waiting_for_go,
            TronServer.State.GAME_STARTED:
                self.handle_game_started,
            TronServer.State.WAITING_FOR_END:
                self.handle_waiting_for_end,
        }

        self.state_msg = {
            TronServer.State.ERR:
                "Server not running",
            TronServer.State.INITIAL:
                "Ready to start TRON server",
            TronServer.State.WAITING_FOR_PLAYERS:
                "Waiting for other players to join",
            TronServer.State.ALL_PLAYERS_CONNECTED:
                "All players connected",
            TronServer.State.WAITING_FOR_GO:
                "Waiting for go from players",
            TronServer.State.GAME_STARTED:
                "Game on!",
            TronServer.State.WAITING_FOR_END:
                "Game ended!",
        }

    def new_round(self):
        self.ready_to_go = [False] * self.num_players
        self.confirmed_end = [False] * self.num_players

        start_config = [
            (self.width // 3 * 1, self.height // 2, 1, 0),
            (self.width // 3 * 2, self.height // 2, -1, 0),
            (self.width // 2, self.height // 3 * 1, 0, 1),
            (self.width // 2, self.height // 3 * 2, 0, -2)
        ]
        for i in range(self.num_players):
            self.player[i] = PlayerModel(*start_config[i])
        self.arena = Arena(self.width, self.width, self.player)

    def num_ready_to_go(self):
        return sum(x is not False for x in self.ready_to_go)

    def num_confirmed_end(self):
        return sum(x is not False for x in self.confirmed_end)

    def run(self, dt):
        self.dt = dt
        if self.state != self.last_state:
            self.last_state = self.state
            print(f"{self.get_state_msg()}")

        handler = self.state_handlers.get(self.state)
        if handler:
            handler()
        else:
            print("No handler for state:", state)

    def get_state_msg(self):
        return f"state: {self.state}: " + self.state_msg[self.state]

    def handle_err(self):
        print(f"{self.get_state_msg()}")
        print("exit")
        sys.exit()

    def handle_initial(self):
        assert self.state == TronServer.State.INITIAL

        self.conn = TronServerConnection(self.host, self.port,
                                         self.num_players)
        if not self.conn.start():
            self.state = TronServer.State.ERR
            return True
        self.state = TronServer.State.WAITING_FOR_PLAYERS
        return True

    def handle_waiting_for_players(self):
        assert self.state == TronServer.State.WAITING_FOR_PLAYERS

        self.conn.update_connections()

        if self.conn.num_joined() == self.num_players:
            self.state = TronServer.State.ALL_PLAYERS_CONNECTED
            return True

        player_index = self.conn.accept_new_connection()
        if player_index >= 0:
            self.conn.send_to_client(player_index, "TRON\n")

        for player_index in range(self.num_players):
            if self.conn.name[player_index] is not None:
                continue
            if (name := self.conn.readline_from_client(player_index)) != "":
                self.conn.name[player_index] = name
                self.conn.send_to_client(player_index, f"ID {player_index}\n")
                print("List of players is now:")
                for i in range(self.num_players):
                    if self.conn.name[i] is not None:
                        print(self.conn.name[i])
        return False

    def handle_all_players_connected(self):
        assert self.state == TronServer.State.ALL_PLAYERS_CONNECTED

        self.new_round()
        self.conn.broadcast(f"ARENA {self.width} {self.height} "
                            f"{self.num_players}\n")
        for player_index in range(self.num_players):
            self.conn.broadcast(f"NAME {player_index} "
                                f"{self.conn.name[player_index]}\n")
        self.conn.broadcast(f"GO\n")

        self.state = TronServer.State.WAITING_FOR_GO
        return True

    def handle_waiting_for_go(self):
        assert self.state == TronServer.State.WAITING_FOR_GO

        for player_index in range(self.num_players):
            if (line := self.conn.readline_from_client(player_index)) != "":
                if line == "GO":
                    self.ready_to_go[player_index] = True
                    self.conn.broadcast(f"R {player_index}\n")

        self.conn.update_connections()

        if self.num_ready_to_go() >= self.conn.num_joined():
            self.conn.broadcast(f"START\n")
            self.state = TronServer.State.GAME_STARTED
            return True
        return False

    def handle_game_started(self):
        assert self.state == TronServer.State.GAME_STARTED

        for player_index in range(self.num_players):
            if (ch := self.conn.getchar_from_client(player_index)) != "":
                if ch == "L":
                    self.player[player_index].rotate_left()
                elif ch == "R":
                    self.player[player_index].rotate_right()
                elif ch == "U":
                    self.player[player_index].accelerate()
                elif ch == "D":
                    self.player[player_index].decelerate()

        self.arena.move_player(self.dt)
        while True:
            msg, more = self.arena.gen_message()
            self.conn.broadcast(msg, newline = False)
            if msg[0] == "E":
                self.state = TronServer.State.WAITING_FOR_END
                return True
            if not more:
                break

        return False

    def handle_waiting_for_end(self):
        assert self.state == TronServer.State.WAITING_FOR_END

        for player_index in range(self.num_players):
            if (line := self.conn.readline_from_client(player_index)) != "":
                if line == "E":
                    self.confirmed_end[player_index] = True

        self.conn.update_connections()

        if self.num_confirmed_end() >= self.conn.num_joined():
            if self.conn.num_joined() == self.num_players:
                self.state = TronServer.State.ALL_PLAYERS_CONNECTED
            else:
                self.state = TronServer.State.WAITING_FOR_PLAYERS
            return True
        return False

#---------------------------------------------------------------------------

def on_segment(p, q, r):
    return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and \
           min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

def orientation(p, q, r):
    val = (q[1] - p[1]) * (r[0] - q[0]) - \
          (q[0] - p[0]) * (r[1] - q[1])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else 2

def segments_intersect(p1, q1, p2, q2):
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and on_segment(p1, p2, q1): return True
    if o2 == 0 and on_segment(p1, q2, q1): return True
    if o3 == 0 and on_segment(p2, p1, q2): return True
    if o4 == 0 and on_segment(p2, q1, q2): return True
    return False


class Arena:
    def __init__(self, width, height, player):
        self.width = width
        self.height = height
        self.running = True
        self.player = player
        self.num_alive = len(self.player)
        self.path = []
        self.msg_queue = collections.deque()
        # for debugging
        self.last_pos = []
        for i, p in enumerate(self.player):
            p.set_arena(self, i)
            self.path.append([(p.x, p.y), (p.x, p.y)])
            self.last_pos.append([p.x, p.y])

    def extend_path(self, player_id, x, y):
        self.path[player_id].append((x, y))

    def collission(self, player_id, x0, y0, x, y):
        if x <= 0 or y <= 0 or x >= self.width - 1 or y >= self.height - 1:
            return True
        for path_index, path in enumerate(self.path):
            skip_last = 3 if path_index == player_id else 1
            for i in range(len(path) - skip_last):
                if segments_intersect((x0, y0), (x, y), path[i], path[i+1]):
                    return True
        return False

    def move_player(self, dt):
        kill = []
        for i, p in enumerate(self.player):
            if not p.alive:
                continue
            x0, y0 = self.path[i][-1]
            p.move(dt)
            self.path[i][-1] = (p.x, p.y)
            if self.collission(i, x0, y0, p.x, p.y):
                kill.append((i, p))
                p.x = max(p.x, 0)
                p.x = min(p.x, self.width - 1)
                p.y = max(p.y, 0)
                p.y = min(p.y, self.width - 1)
        for i, p in kill:
            p.alive = False
            self.path[i] = []
            self.collision = True
            self.num_alive -= 1
            self.msg_queue.append(f"D {i}\n")

    def gen_message(self):
        if len(self.msg_queue):
            return (self.msg_queue.popleft(), True)
        elif self.num_alive > 1:
            msg = "P"
            for i, p in enumerate(self.player):
                msg += f" {p.x:.2f} {p.y:.2f}"

                if p.x != self.last_pos[i][0] and p.y != self.last_pos[i][1]:
                    raise RuntimeError(f"Player {i}: last pos "
                                       f"{self.last_pos[i]} "
                                       f"new pos {p.x} {p.y}")
                self.last_pos[i][0] = p.x
                self.last_pos[i][1] = p.y
            return (msg + "\n", False)
        elif self.num_alive <= 1:
            self.running = False
            for i, p in enumerate(self.player):
                if p.alive:
                    return (f"E {i}\n", False)
            return (f"E {-1}\n", False)
        else:
            return (None, False)

class PlayerModel:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.speed = SPEED_INITIAL
        self.alive = True
        self.arena = None
        self.player_id = None

    def set_arena(self, arena, player_id):
        self.arena = arena
        self.player_id = player_id

    def rotate_left(self):
        self.dx, self.dy = self.dy, -self.dx
        self.arena.extend_path(self.player_id, self.x, self.y)

    def rotate_right(self):
        self.dx, self.dy = -self.dy, self.dx
        self.arena.extend_path(self.player_id, self.x, self.y)

    def accelerate(self):
        if self.speed < len(SPEED) - 1:
            self.speed += 1

    def decelerate(self):
        if self.speed > 0:
            self.speed -= 1

    def move(self, dt):
        if not self.alive:
            return

        self.x += self.dx * SPEED[self.speed] * dt * 60
        self.y += self.dy * SPEED[self.speed] * dt * 60

#---------------------------------------------------------------------------

def main(argv):
    width, height, num_players = WIDTH, HEIGHT, NUM_PLAYERS

    if len(argv) > 2:
        width, height = int(argv[1]), int(argv[2])
    if len(argv) > 3:
        num_players = int(argv[3])

    tron_server = TronServer(HOST, PORT, width, height, num_players)

    last_time = time.time()
    while True:
        now = time.time()
        dt = now - last_time
        last_time = now

        tron_server.run(dt)

        time.sleep(max(0, 1.0 / FPS - (time.time() - now)))

main(sys.argv)
