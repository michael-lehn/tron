import collections
import select
import socket
import time

FPS = 60

HOST = '0.0.0.0'
PORT = 65432
WIDTH, HEIGHT = 3000, 3000

SPEED = (0.1, 0.3, 0.7, 0.9, 1.0, 1.1, 1.3, 1.7, 2.5, 4.1)
SPEED_INITIAL = 4

class ServerStuff:
    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen(2)

        print(f"TRON server running on {self.HOST}:{self.PORT}")
        print("Waiting for two players...")

        self.conn = [None, None]

        for i in range(0, 2):
            self.conn[i], addr = self.sock.accept()
            self.conn[i].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"Player {i + 1} connected from", addr)
            self.conn[i].setblocking(False)
            self.conn[i].sendall(f"I {i}\n".encode('utf-8'))

    def broadcast(self, msg):
        for conn in self.conn:
            try:
                conn.sendall(msg.encode('utf-8'))
            except:
                return False
        return True

    def read(self):
        try:
            readable, _, _ = select.select(self.conn, [], [], 0)
            for conn in readable:
                data = conn.recv(1)
                if not data:
                    raise ConnectionError("Disconnected")
                cmd = data.decode('utf-8').strip().upper()
                player = self.conn.index(conn)
                return (True, player, cmd)
        except (ConnectionResetError, BrokenPipeError):
            print("Player disconnected.")
            return None
        except Exception as e:
            print("Unexpected error in read():", type(e).__name__, e)
            return None
        return (False, )

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
        self.player = player
        self.running = True
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
            print(f"Player {i} collided!")
            print(f"{self.num_alive} players left")

    def gen_message(self):
        if len(self.msg_queue):
            return self.msg_queue.popleft()
        elif self.num_alive > 1:
            msg = "P"
            for i, p in enumerate(self.player):
                msg += f" {p.x:.2f} {p.y:.2f}"
                if p.x != self.last_pos[i][0] and p.y != self.last_pos[i][1]:
                    raise RuntimeError(f"Player {i}: last pos "
                                       f"{self.last_pos[i]} "
                                       f"new pos {p}")
                self.last_pos[i][0] = p.x
                self.last_pos[i][1] = p.y
            msg += "\n"
            return msg
        else:
            self.running = False
            return "E\n"

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


def main():
    serverStuff = ServerStuff("0.0.0.0", 65432)

    while True:
        player = []
        player.append(PlayerModel(WIDTH // 2 - 200, HEIGHT // 2, 1, 0))
        player.append(PlayerModel(WIDTH // 2 + 200, HEIGHT // 2, -1, 0))
        arena = Arena(WIDTH, HEIGHT, player)

        serverStuff.broadcast("S\n")
        time.sleep(3)
        print("Game started!")

        last_time = time.time()
        while arena.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            line = serverStuff.read()
            if line is None:
                return
            elif line[0] is True:
                _, id, cmd = line
                if cmd == "L":
                    player[id].rotate_left()
                elif cmd == "R":
                    player[id].rotate_right()
                elif cmd == "U":
                    player[id].accelerate()
                elif cmd == "D":
                    player[id].decelerate()
                elif cmd == "Q":
                    print("Player quit")
                    return

            arena.move_player(dt)

            if not serverStuff.broadcast(arena.gen_message()):
                print("Can not broadcast")

            time.sleep(max(0, 1.0 / FPS - (time.time() - now)))

main()
