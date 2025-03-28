import math
import pygame
import select
import socket
import sys
import time

PORT = 65432
FPS = 120 


ARENA_WIDTH, ARENA_HEIGHT = 1000, 1000
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
ANGLE_STEP = 3 

C_PLAYER = [ (0, 255, 255),  # cyan
             (255, 100, 0)   # orange
           ]
C_ARENA = (50, 50, 50)
C_DEAD = (55, 10, 10)
C_GRID = (200, 200, 200)


class InternetStuff:

    def __init__(self, ip, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))
        self.sock.setblocking(False)
        self.buffer = ""

    def __del__(self):
        self.sock.close()

    def send(self, msg):
        try:
            self.sock.sendall(msg.encode("utf-8"))
            return True
        except (BrokenPipeError, ConnectionResetError) as e:
            print("Send failed (disconnected):", type(e).__name__, e)
        except Exception as e:
            print("Unexpected error in send():", type(e).__name__, e)
        return False

    def read(self):
        try:
            readable, _, _ = select.select([self.sock], [], [], 0)
            if self.sock in readable:
                data = self.sock.recv(64)
                if not data:
                    print("Disconnected from server.")
                    return None

                try:
                    self.buffer += data.decode("utf-8")
                except UnicodeDecodeError as e:
                    print("Decode error – possibly corrupted data:", e)
                    return None
        except BlockingIOError:
            print("BlockingIOError: no data available right now")
        except ConnectionResetError:
            print("Connection reset by peer.")
            return None
        except Exception as e:
             print("Ignored error in read():", type(e), e)

        if "\n" in self.buffer:
            cmd, self.buffer = self.buffer.split("\n", 1)
            cmd = cmd.split()
            if len(cmd) == 5 and cmd[0] == "P":
                cmd[1:] = [float(x) for x in cmd[1:]]
            else:
                cmd[1:] = [int(x) for x in cmd[1:]]
            return cmd
        return ("",)

def sign(x):
    return (x > 0) - (x < 0)

def angle_between(u, v):
    if u[0] == v[0] and u[0] == v[0]:
        return 0
    if u[0] == v[1] and u[1] == -v[0]:
        return 90
    elif u[0] == -v[1] and u[1] == v[0]:
        return -90
    else:
        print(f"u = {u}, v = {v}")
        raise ValueError("Only special cases are handled")

class PlayerViewer:

    def __init__(self, color):
        self.color = color
        self.path = []
        self.dx = 0
        self.dy = -1
        self.angle = 0
        self.angle_turn = 0
        self.x = None
        self.y = None
        self.alive = True

    def draw(self, surface):
        for i in range(len(self.path)-1):
            x0, y0 = self.path[i]
            x1, y1 = self.path[i + 1]
            pygame.draw.line(surface, self.color, (x0, y0), (x1, y1), 3)
        if self.angle_turn > 0:
            self.angle += ANGLE_STEP
            self.angle_turn -= ANGLE_STEP
        elif self.angle_turn < 0:
            self.angle -= ANGLE_STEP
            self.angle_turn += ANGLE_STEP

    def set_position(self, x, y):
        self.x, self.y = x, y
        if len(self.path) == 0:
            self.path = [ (self.x, self.y) ]
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

class ArenaViewer:

    def __init__(self, width, height):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))

        pygame.display.set_caption("TRON Client")
        self.clock = pygame.time.Clock()

        self.world = pygame.Surface((ARENA_WIDTH * 2, ARENA_HEIGHT * 2))
        self.arena = pygame.Surface((ARENA_WIDTH, ARENA_HEIGHT))
        self.cropped = pygame.Surface((self.width, self.height))
        self.arena_padding = (ARENA_WIDTH // 2, ARENA_HEIGHT // 2)
        self.arena_viewport = pygame.Rect(0, 0, ARENA_WIDTH, ARENA_HEIGHT)
        self.screen_viewport = pygame.Rect(0, 0, self.width, self.height)
        self.i_am = None
        self.new_round()

        self.grid = pygame.Surface((ARENA_WIDTH, ARENA_HEIGHT))
        self.grid.fill(C_ARENA)
        for x in range(0, ARENA_WIDTH, 50):
            pygame.draw.line(self.grid, C_GRID, (x, 0), (x, ARENA_HEIGHT))
        for y in range(0, ARENA_HEIGHT, 50):
            pygame.draw.line(self.grid, C_GRID, (0, y), (ARENA_WIDTH, y))

    def __del__(self):
        pygame.quit()

    def new_round(self):
        self.player = []
        self.i_am_alive = True

    def add_player(self, p):
        self.player.append(p)

    def del_player(self, player_index):
        if self.i_am == player_index:
            self.i_am_alive = False
        self.player[player_index].alive = False

    def set_position(self, pos_list):
        for i, p in enumerate(self.player):
            if p is not None:
                p.set_position(pos_list[2*i], pos_list[2*i + 1])

    def i_am_player(self, index):
        self.i_am = index

    def next_frame(self):
        if self.i_am_alive:
            self.arena.blit(self.grid, (0, 0))
        else:
            self.arena.fill(C_DEAD)

        border_color = (255, 0, 0)
        border_rec = pygame.Rect(0, 0, ARENA_WIDTH, ARENA_HEIGHT) 
        pygame.draw.rect(self.arena, border_color, border_rec, 1)

        for i, p in enumerate(self.player):
            if p.alive:
                p.draw(self.arena)

        if self.i_am is not None and self.i_am < len(self.player) \
                and self.player[self.i_am] is not None \
                and self.player[self.i_am].x is not None:
            x = self.player[self.i_am].x
            y = self.player[self.i_am].y
            angle = self.player[self.i_am].angle

            self.world.blit(self.arena, self.arena_padding)
            self.arena_viewport.center = (x + self.arena_padding[0],
                                          y + self.arena_padding[1])
            self.cropped = self.world.subsurface(self.arena_viewport)
            rotated = pygame.transform.rotate(self.cropped, angle)
            self.screen_viewport.center = rotated.get_rect().center
            rotated = rotated.subsurface(self.screen_viewport)
            self.screen.blit(rotated, (0,0))

        pygame.display.flip()
        self.clock.tick(FPS)


def main(argv):
    if len(argv) != 2:
        print(f"Usage: python {sys.argv[0]} <server-ip>")
        sys.exit(1)
    SERVER_IP = argv[1]

    arenaViewer = ArenaViewer(SCREEN_WIDTH, SCREEN_HEIGHT)
    internetStuff = InternetStuff(SERVER_IP, PORT)

    fullscreen = False
    playing = True
    while playing:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                playing = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    playing = False
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
                else:
                    keymap = {
                        pygame.K_LEFT: "L",
                        pygame.K_RIGHT: "R",
                        pygame.K_UP: "U",
                        pygame.K_DOWN: "D",
                        pygame.K_q: "Q"
                    }
                    if event.key in keymap:
                        cmd = keymap[event.key]
                        if cmd == "Q":
                            internetStuff.send("Q")
                            return False
                        else:
                            if not internetStuff.send(cmd):
                                return False

        got = internetStuff.read()

        if got is None or got[0] == "Q":
            return False
        elif got[0] == "I":
            print(f"I am Player {got[1]}")
            arenaViewer.i_am_player(got[1])
        elif got[0] == "P":
            arenaViewer.set_position(got[1:])
        elif got[0] == "S":
            arenaViewer.new_round()
            arenaViewer.add_player(PlayerViewer(C_PLAYER[0]))
            arenaViewer.add_player(PlayerViewer(C_PLAYER[1]))
        elif got[0] == "D":
            arenaViewer.del_player(got[1])
            print(f"Player {got[1]} is deleted")
        elif got[0] == "E":
            print("Round ended")

        arenaViewer.next_frame()
    return True

main(sys.argv)
