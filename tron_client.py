import select
import socket
import time
import random
import threading

from enum import Enum, auto

def get_local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        subnet = ".".join(local_ip.split(".")[:3]) + "."
        return subnet
    except:
        return "192.168.0."

class ServerScanner:

    def __init__(self, timeout=0.2, port=65432):
        self.timeout = timeout
        self.port = port
        self.found = []
        self.search_done = None
        self._lock = threading.Lock()
        self.start_scan()

    def start_scan(self):
        with self._lock:
            if self.search_done is None or self.search_done:
                print("Scanning for servers in local network")
                self.search_done = False
                self._thread = threading.Thread(target=self._scan,
                                                daemon=True)
                self._thread.start()

    def _scan(self):
        test_ips = ["127.0.0.1"]
        base_ip = get_local_subnet()
        test_ips.extend(base_ip + str(i) for i in range(1, 255))

        print(f"Scanning {base_ip}0/24 and "
              f"localhost on port {self.port}...")

        for ip in test_ips:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(self.timeout)
                    s.connect((ip, self.port))
                    banner = s.recv(16).decode("utf-8").strip()
                    if banner == "TRON":
                        self.add(ip)
            except (socket.timeout, ConnectionRefusedError, OSError):
                continue
            except Exception as e:
                print(f"Error at {ip}: {type(e).__name__} – {e}")
        self.search_completed(True)

    def add(self, ip):
        with self._lock:
            if ip not in self.found:
                self.found.append(ip)

    def get_found(self):
        with self._lock:
            return list(self.found)

    def search_completed(self, done = None):
        with self._lock:
            if done is not None:
                self.search_done = True
            return self.search_done

class TronClientConnection:
    def __init__(self, ip, port):
        self.buffer = ""
        self.line_ready = False
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, self.port))

    def __del__(self):
        if self.sock is not None:
            self.sock.close()

    def check_banner(self):
        banner = self.readline()
        if banner == "":
            return None
        if banner != "TRON":
            print(f"Server at {self.ip}:{self.port} is not a TRON server.")
            return False
        return True

    def send(self, msg):
        try:
            self.sock.sendall(msg.encode("utf-8"))
            return True
        except (BrokenPipeError, ConnectionResetError) as e:
            print("Send failed (disconnected):", type(e).__name__, e)
        except Exception as e:
            print("Unexpected error in send():", type(e).__name__, e)
        return False

    def readline(self):
        try:
            readable, _, _ = select.select([self.sock], [], [], 0)
            if self.sock in readable:
                data = self.sock.recv(64)
                if not data:
                    print("Disconnected from server.")
                    return None
                self.buffer += data.decode("utf-8")
        except (BlockingIOError, ConnectionResetError, OSError) as e:
            print("Error during readline:", type(e).__name__, e)
            return None

        if "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            return line.strip()

        return ""

class TronClient:

    class State(Enum):
        ERR_SERVER_CONNECTION = auto()      # can not connect
        ERR_NOT_TRON_SERVER = auto()        # not a TRON server
        ERR_CONNECTION_LOST = auto()        # connection lost
        NOT_CONNECTED = auto()
        CONNECTED = auto()
        WAITING_FOR_ID = auto()
        WAITING_FOR_GO = auto()
        RECEIVED_GO = auto()
        RECEIVED_START = auto()
        RECEIVED_END = auto()

    def __init__(self, viewer = None):
        self.state = TronClient.State.NOT_CONNECTED
        self.arena = Arena()
        self.ready_to_go = False
        self.ready_to_end = False
        self.last_state = None
        self.viewer = viewer

        ## NOT_CONNECTED -> CONNECTED
        self.host = None                # required
        self.port = None                # required
        self.conn = None                # set

        # CONNECTED -> WAITING_FOR_GO
        self.name = None                # required

        # WAITING_FOR_GO -> RECEIVED_GO

        self.state_handlers = {
            TronClient.State.ERR_SERVER_CONNECTION: self.handle_err,
            TronClient.State.ERR_NOT_TRON_SERVER: self.handle_err,
            TronClient.State.ERR_CONNECTION_LOST: self.handle_err,
            TronClient.State.NOT_CONNECTED: self.handle_not_connected,
            TronClient.State.CONNECTED: self.handle_connected,
            TronClient.State.WAITING_FOR_ID: self.handle_waiting_for_id,
            TronClient.State.WAITING_FOR_GO: self.handle_waiting_for_go,
            TronClient.State.RECEIVED_GO: self.handle_received_go,
            TronClient.State.RECEIVED_START: self.handle_received_start,
            TronClient.State.RECEIVED_END: self.handle_received_end,
        }

        self.state_msg = {
            TronClient.State.ERR_SERVER_CONNECTION:
                lambda: f"Can not connect to server",
            TronClient.State.ERR_NOT_TRON_SERVER:
                lambda: f"Not a TRON server",
            TronClient.State.ERR_CONNECTION_LOST:
                lambda: f"Connection to server {self.host} lost",
            TronClient.State.NOT_CONNECTED:
                lambda: f"Not connected",
            TronClient.State.CONNECTED:
                lambda: f"Connected to server {self.host}",
            TronClient.State.WAITING_FOR_ID:
                lambda: f"Waiting for my id number",
            TronClient.State.WAITING_FOR_GO:
                lambda: f"Waiting for others to be ready to play",
            TronClient.State.RECEIVED_GO:
                lambda: f"Press any key for next round",
            TronClient.State.RECEIVED_START:
                lambda: f"Game on!",
            TronClient.State.RECEIVED_END:
                lambda: f"That’s it for this round!",
        }

    def get_state_msg(self):
        #return f"state: {self.state}: " + self.state_msg[self.state]
        return self.state_msg[self.state]()

    def not_connected(self):
        if self.state == TronClient.State.ERR_SERVER_CONNECTION:
            return True
        elif self.state == TronClient.State.ERR_NOT_TRON_SERVER:
            return True
        elif self.state == TronClient.State.ERR_CONNECTION_LOST:
            return True
        elif self.state == TronClient.State.NOT_CONNECTED:
            return True
        return False

    def received_go(self):
        if self.state != TronClient.State.RECEIVED_GO:
            return False
        return True

    def received_end(self):
        if self.state != TronClient.State.RECEIVED_END:
            return False
        return True

    def game_is_on(self):
        return self.state == TronClient.State.RECEIVED_START

    def send_move(self, move):
        if self.state != TronClient.State.RECEIVED_START:
            return False
        if not self.conn.send(move):
            self.state = TronClient.State.ERR_CONNECTION_LOST
            return False
        return True

    def connect(self, host, port, name):
        self.host = host
        self.port = port
        self.name = name
        self.conn = None
        self.state = TronClient.State.NOT_CONNECTED

    def run(self):
        if self.state != self.last_state:
            self.last_state = self.state

        handler = self.state_handlers.get(self.state)
        if handler:
            handler()
        else:
            print("No handler for state:", state)

    def handle_err(self):
        self.conn = None
        self.host = None
        self.state = TronClient.State.NOT_CONNECTED
        return True

    def handle_not_connected(self):
        assert self.state == TronClient.State.NOT_CONNECTED

        if self.host is None or self.port is None:
            return False

        if self.conn is None:
            try:
                self.conn = TronClientConnection(self.host, self.port)
            except Exception as e:
                self.state = TronClient.State.ERR_SERVER_CONNECTION
                return True
        else:
            banner = self.conn.check_banner()
            if banner is None:
                self.state = TronClient.State.ERR_SERVER_CONNECTION
                return True
            if not banner:
                self.state = TronClient.State.ERR_NOT_TRON_SERVER
                return True
            
        assert self.conn is not None
        self.state = TronClient.State.CONNECTED
        return True

    def handle_connected(self):
        assert self.state == TronClient.State.CONNECTED

        if self.name == None:
            return False

        if not self.conn.send(self.name + "\n"):
            self.state = TronClient.State.ERR_CONNECTION_LOST
            return True


        self.state = TronClient.State.WAITING_FOR_ID
        return True

    def handle_waiting_for_id(self):
        assert self.state == TronClient.State.WAITING_FOR_ID

        line = self.conn.readline()
        if line is None:
            self.state = TronClient.State.ERR_CONNECTION_LOST
            return True
        line = line.split()
        if len(line) == 0:
            return False
        elif line[0] == "ID":
            self.arena.I_am_player = int(line[1])
            self.state = TronClient.State.WAITING_FOR_GO
            return True
        return False

    def handle_waiting_for_go(self):
        assert self.state == TronClient.State.WAITING_FOR_GO

        line = self.conn.readline()
        if line is None:
            self.state = TronClient.State.ERR_CONNECTION_LOST
            return True
        line = line.split()
        if len(line) == 0:
            return False
        print(f"{line}")
        if line[0] == "GO":
            self.state = TronClient.State.RECEIVED_GO
            return True
        elif line[0] == "ARENA":
            self.arena.set_dim(int(line[1]), int(line[2]), int(line[3]))
            if self.viewer is not None:
                self.viewer.new_arena()
        elif line[0] == "NAME":
            self.arena.add_player(int(line[1]), line[2])
        return False

    def handle_received_go(self):
        assert self.state == TronClient.State.RECEIVED_GO

        if self.ready_to_go:
            self.ready_to_go = False
            if not self.conn.send("GO\n"):
                self.state = TronClient.State.ERR_CONNECTION_LOST
                return True
            # now waiting for START

        line = self.conn.readline()
        if line is None:
            self.state = TronClient.State.ERR_CONNECTION_LOST
            return True
        line = line.split()
        if len(line) == 0:
            return False
        print(f"{line}")
        if line[0] == "START":
            self.state = TronClient.State.RECEIVED_START
            return True
        elif line[0] == "R":
            if self.arena.ready is not None:
                self.arena.ready[int(line[1])] = True
        return False

    def handle_received_start(self):
        assert self.state == TronClient.State.RECEIVED_START

        MAX_POSITION_READS = 42
        for i in range(MAX_POSITION_READS):
            line = self.conn.readline()
            if line is None:
                self.state = TronClient.State.ERR_CONNECTION_LOST
                return True
            line = line.split()
            if len(line) == 0:
                return False
            if line[0] == "P":
                self.arena.set_position(line[1:])
            elif line[0] == "D":
                self.arena.del_player(int(line[1]))
            elif line[0] == "E":
                self.arena.end_round(int(line[1]))
                if self.viewer is not None:
                    self.viewer.end_round(int(line[1]))
                self.state = TronClient.State.RECEIVED_END
                return True

        return False

    def handle_received_end(self):
        assert self.state == TronClient.State.RECEIVED_END

        if self.ready_to_end:
            self.ready_to_end = False
            if not self.conn.send("\nE\n"):
                self.state = TronClient.State.ERR_CONNECTION_LOST
                return True

            self.state = TronClient.State.WAITING_FOR_GO
            return True
        return False

def sign(x):
    return (x > 0) - (x < 0)

def angle_between(u, v):
    if u[0] == v[0] and u[1] == v[1]:
        return 0
    elif u[0] == v[1] and u[1] == -v[0]:
        return 90
    elif u[0] == -v[1] and u[1] == v[0]:
        return -90
    elif u[0] == -v[0] and u[1] == -v[1]:
        return 180
    else:
        print(f"u = {u}, v = {v}")
        raise ValueError("Only special cases are handled")

class Player:
    def __init__(self):
        self.path = None
        self.x, self.y = None, None
        self.dx, self.dy = 0, -1
        self.angle = 0
        self.angle_turn = 0

    def get_angle(self):
        ANGLE_STEP = 5

        if self.angle_turn > 0:
            self.angle += ANGLE_STEP
            self.angle_turn -= ANGLE_STEP
        elif self.angle_turn < 0:
            self.angle -= ANGLE_STEP
            self.angle_turn += ANGLE_STEP
        return self.angle

    def set_position(self, x, y):
        self.x, self.y = x, y
        if self.path is None:
            self.path = [ (x, y), (x, y) ]

        last_x, last_y = self.path[-1]
        dx = sign(self.x - last_x)
        dy = sign(self.y - last_y)

        if dx == 0 and dy == 0:
            return

        if dx == self.dx and dy == self.dy:
            self.path[-1] = (self.x, self.y)
        else:
            self.path.append((self.x, self.y))
            self.angle_turn += angle_between((self.dx, self.dy), (dx, dy))
            self.dx = dx
            self.dy = dy

class Arena:

    def __init__(self):
        self.width, self.height = None, None
        self.player = None
        self.name = None
        self.score = None
        self.ready = None
        self.ready = None
        self.I_am_player = None

    def set_dim(self, width, height, num_players):
        self.width, self.height = width, height
        if self.player is None or len(self.player) != num_players:
            self.player = [None] * num_players
            self.name = [None] * num_players
            self.score = [0] * num_players
            self.ready = [False] * num_players

    def add_player(self, player_index, player_name):
        self.player[player_index] = Player()
        if self.name[player_index] != player_name:
            self.name[player_index] = player_name
            self.score[player_index] = 0
        self.ready[player_index] = False

    def del_player(self, player_index):
        self.player[player_index] = None

    def end_round(self, winner_index = -1):
        for i in range(len(self.score)):
            self.ready[i] = False
            if i == winner_index:
                self.score[i] += 1

    def set_position(self, pos_list):
        for i, p in enumerate(self.player):
            if p is not None:
                p.set_position(float(pos_list[2 * i]),
                               float(pos_list[2 * i + 1]))

    def print(self):
        if self.player is None:
            return
        if self.I_am_player is not None:
            print(f"I am player {self.I_am_player} "
                  f"{self.name[self.I_am_player]}")
        else:
            print(f"I am player ?")
        for i, p in enumerate(self.player):
            print(f"{self.score[i]}", end='')
            if self.ready[i]:
                print(f"> ", end='')
            else:
                print(f"? ", end='')
            print(f"{self.name[i]}: ", end='', flush=True)
            if self.player[i] is not None:
                if self.player[i].path is not None:
                    print(f"{self.player[i].path[-4:]}", end='', flush=True)
            print(flush=True)

def main():
    tron_client = TronClient()
    name = input("Name: ")
    if name == "":
        name = "Mick"

    moves = "LRUD"

    while True:
        if tron_client.host is None:
            host = input("Host: ")
            if host == "":
                host = "localhost"
            tron_client.connect(host, 65432, name)

        tron_client.run()

        if tron_client.received_go():
            x = input("Press 'q' to exit, any other key to play: ")
            if x == "q":
                break
            tron_client.ready_to_go = True

        print("\033[2J\033[H", end='') # clear screen
            
        
        status = tron_client.get_state_msg()
        print(f"status = '{status}'", flush=True)

        if tron_client.game_is_on() and random.random() < 0.02:
            move = random.choice(moves)
            print(f"Move chosen: {move}")
            tron_client.send_move(move)

        if tron_client.arena is not None:
            tron_client.arena.print()
        time.sleep(1 / 40)

if __name__ == '__main__':
    main()
