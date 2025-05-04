import math
import pygame
import serial
import sys
from tron_client import TronClient
from tron_client import ServerScanner
import serial.tools.list_ports
import getpass

C_PLAYER = [
    (111, 226, 226), # cyan (Player 1)
    (242, 160, 7),   # orange (Player 2)
    (180, 0, 255),   # neon purple (Player 3)
    (0, 255, 128)    # turquoise green (Player 4)
]

C_ARENA = (50, 50, 50)
C_DEAD = (55, 10, 10)
C_GRID = (200, 200, 200)

class Tron2D:

    def __init__(self, fps, width, height):
        self.fps = fps
        self.width, self.height = width, height

        self.name = getpass.getuser()
        self.host = "localhost"
        self.port = 65432
        self.edit = 0
        self.server_scanner = ServerScanner()
        self.server_scanner.start_scan()
        self.serverlist_i = 0
        self.serverlist_i0 = 0

        self.winner = None

        ser_dev = next(
            (p.device for p in serial.tools.list_ports.comports()
                if p.device.startswith("/dev/cu.usbserial")),
            None
        )
        self.ser = None
        if ser_dev is not None:
            try:
                self.ser = serial.Serial(ser_dev, 9600, timeout=0)
                self.ser.write(b'X')
            except:
                print(f"can not open serial device {ser_dev}")

        self.tron_client = TronClient(self)

        pygame.init()
        pygame.display.set_caption("TRON: Lightcycle 2D")

        fonts = pygame.font.get_fonts()
        for name in sorted(fonts):
            print(name)
        
        mono_fonts = ["andalemono", "consolas", "couriernew", "monospace"]
        normal_fonts = ["helvetica", "timesnewroman", "monospace"]

        self.title_font = pygame.font.SysFont(normal_fonts, 48)
        self.score_font = pygame.font.SysFont(mono_fonts, 20)
        self.state_font = pygame.font.SysFont(mono_fonts, 24, italic=True)
        self.winner_font = pygame.font.SysFont(normal_fonts, 60)
        self.input_font = pygame.font.SysFont(mono_fonts, 32)
        self.hint_font = pygame.font.SysFont(mono_fonts, 18)
        self.list_font = pygame.font.SysFont(mono_fonts, 18)

        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        self.s_arena = None
        self.s_world = None
        self.s_grid = None

    def __del__(self):
        pygame.quit()

    def new_arena(self):
        print("new arena")

        arena = self.tron_client.arena
        self.s_arena = pygame.Surface((arena.width, arena.height))
        self.s_world = pygame.Surface((arena.width * 2, arena.height * 2))
        self.arena_viewport = pygame.Rect(0, 0, arena.width, arena.height)
        self.arena_padding = (arena.width // 2, arena.height // 2)

        self.s_grid = pygame.Surface((arena.width, arena.height))
        self.s_grid.fill(C_ARENA)
        for x in range(0, arena.width, 50):
            pygame.draw.line(self.s_grid, C_GRID, (x, 0), (x, arena.height))
        for y in range(0, arena.height, 50):
            pygame.draw.line(self.s_grid, C_GRID, (0, y), (arena.width, y))

        self.screen_crop = None
        w, h = min(self.width, arena.width), min(self.height, arena.height)
        self.screen_viewport = pygame.Rect(0, 0, w, h)

    def focus_coords(self):
        assert self.tron_client.arena is not None

        arena = self.tron_client.arena
        x, y, angle = arena.width // 2, arena.height // 2, 0

        if arena.I_am_player is not None \
                and arena.player[arena.I_am_player] is not None \
                and arena.player[arena.I_am_player].x is not None:
            x = arena.player[arena.I_am_player].x
            y = arena.player[arena.I_am_player].y
            angle = arena.player[arena.I_am_player].get_angle()

        return (x, y, angle)

    def end_round(self, winner):
        assert self.tron_client.arena is not None

        arena = self.tron_client.arena
    
        msg = "All dead! No winner!"
        color = (255, 255, 255)
        if winner >= 0:
            msg = f"{arena.name[winner]} won"
            color = C_PLAYER[winner]
        print(msg)
        self.winner = self.winner_font.render(msg, True, color)

    def show_connect(self):
        title_text = self.title_font.render("TRON: Lightcycle", True,
                                            (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.width // 2, 80))
        self.screen.blit(title_text, title_rect)

        prompt_name = self.input_font.render("Name:", True, (100, 200, 100))
        input_name = self.input_font.render(self.name
            + ("‸" if self.edit == 0 else ""), True, (155, 255, 155))
        self.screen.blit(prompt_name, (self.width // 5, 180))
        self.screen.blit(input_name,   (self.width // 5 + 150, 180))

        prompt_server = self.input_font.render("Server:", True, (100, 200, 100))
        input_server = self.input_font.render(self.host
            + ("‸" if self.edit == 1 else ""), True, (155, 255, 155))
        self.screen.blit(prompt_server, (self.width // 5, 230))
        self.screen.blit(input_server,   (self.width // 5 + 150, 230))

        hint = ("^Q: Quit  |  TAB: switch field  |  ^F: find server  "
                "|  RETURN: connect")
        hint_text = self.hint_font.render(hint, True, (150, 150, 150))
        hint_rect = hint_text.get_rect(center=(self.width // 2,
                                               self.height - 80))
        self.screen.blit(hint_text, hint_rect)

    def get_serverlist(self):
        return self.server_scanner.get_found()

    def show_serverlist(self):
        title_text = self.title_font.render(
                "TRON servers in local network", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.width // 2, 80))
        self.screen.blit(title_text, title_rect)

        server_list = self.get_serverlist()
        if len(server_list) != 0:
            self.serverlist_i %= len(server_list)

        max_items = 3

        if self.serverlist_i < self.serverlist_i0:
            self.serverlist_i0 = self.serverlist_i
        elif self.serverlist_i >= self.serverlist_i0 + max_items:
            self.serverlist_i0 = self.serverlist_i - max_items + 1

        lx, ly = self.width // 2 - 150, self.height // 3
        if self.serverlist_i0 > 0:
            pygame.draw.polygon(self.screen, (0, 255, 255),
                                [(lx+5, ly-15), (lx+25, ly-15), (lx+15, ly-25)])
        if self.serverlist_i0 + max_items < len(server_list):
            Ly = ly + max_items * 40
            pygame.draw.polygon(self.screen, (0, 255, 255),
                                [(lx+5, Ly), (lx+25, Ly), (lx+15, Ly+10)])

        server_list = server_list[self.serverlist_i0 :
                                  self.serverlist_i0 + max_items ]

        for i0, addr in enumerate(server_list):
            i = self.serverlist_i0 + i0
            color = (0, 255, 255) if i == self.serverlist_i else (180, 180, 180)
            entry = self.list_font.render(f"({i}) " + addr, True, color)
            self.screen.blit(entry, (lx, ly + i0 * 40))

        hint = "ESC: Cancle  |  RETURN: select  |  ↑↓:  up / down"
        hint_text = self.hint_font.render(hint, True, (150, 150, 150))
        hint_rect = hint_text.get_rect(center=(self.width // 2,
                                               self.height - 80))
        self.screen.blit(hint_text, hint_rect)

    def show_state(self):
        state = self.tron_client.get_state_msg()
        state_text = self.state_font.render(state, True, (150, 150, 150))
        state_rect = state_text.get_rect(center=(self.width // 2,
                                                 self.height - 40))
        self.screen.blit(state_text, state_rect)
        
    def show_score(self):
        padding = 10
        y = padding
        arena = self.tron_client.arena

        if arena is None or arena.player is None:
            return

        for i, p in enumerate(arena.player):
            color = (100, 150, 50)
            if arena.ready[i]:
                color = C_PLAYER[i]
            text = f"{arena.name[i]}: {arena.score[i]}"
            if arena.I_am_player is not None and i == arena.I_am_player:
                text = "> " + text
            else:
                text = "  " + text
            label = self.score_font.render(text, True, color)
            self.screen.blit(label, (padding, y))
            y += label.get_height() + 5

        if self.winner is not None:
            winner_rect = self.winner.get_rect(center=(self.width // 2,
                                                       self.height // 2))
            self.screen.blit(self.winner, winner_rect)

    def show_arena(self):
        assert self.tron_client.arena is not None

        arena = self.tron_client.arena

        self.s_arena.blit(self.s_grid, (0, 0))

        border_color = (255, 0, 0)
        border_rec = pygame.Rect(0, 0, arena.width, arena.height) 
        pygame.draw.rect(self.s_arena, border_color, border_rec, 1)

        for pi, p in enumerate(arena.player):
            if p is None or p.path is None:
                continue
            for i in range(len(p.path) - 1):
                x0, y0 = p.path[i]
                x1, y1 = p.path[i + 1]
                pygame.draw.line(self.s_arena, C_PLAYER[pi],
                                 (x0, y0), (x1, y1), 3)

        x, y, angle = self.focus_coords()

        self.s_world.blit(self.s_arena, self.arena_padding)
        self.arena_viewport.center = (x + self.arena_padding[0],
                                      y + self.arena_padding[1])

        self.screen_crop = self.s_world.subsurface(self.arena_viewport)
        rotated = pygame.transform.rotate(self.screen_crop, angle)
        self.screen_viewport.center = rotated.get_rect().center
        rotated = rotated.subsurface(self.screen_viewport)
        self.screen.blit(rotated, (0,0))

    def run(self):
        in_select_server = False
        while True:
            self.tron_client.run()
            self.screen.fill((0, 0, 0))
            if self.tron_client.not_connected() or self.s_arena is None:
                if in_select_server:
                    self.show_serverlist()
                else:
                    self.show_connect()
            else:
                self.show_arena()
                self.show_score()
            self.show_state()

            if self.ser is not None and self.ser.in_waiting > 0:
                ch = self.ser.read(1)
                print(f"get form serial {ch}")
                if ch == b"A":
                    if self.tron_client.game_is_on():
                        self.tron_client.send_move("L")
                elif ch == b"B":
                    if self.tron_client.game_is_on():
                        self.tron_client.send_move("R")
                elif ch == b"X":
                    while self.ser.in_waiting < 4:
                        pass
                    val = int(self.ser.read(4).decode('utf-8'))
                    print(f"val = {val}")
                    if not hasattr(self, "oldXSerVal"):
                        self.oldXSerVal = val
                    if val > self.oldXSerVal:
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("U")
                    elif val < self.oldXSerVal:
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("D")
                    self.ser.write(b'X')

            for event in pygame.event.get():
                mods = pygame.key.get_mods()
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q and (mods & pygame.KMOD_CTRL):
                        return
                    elif self.tron_client.not_connected():
                        if in_select_server:
                            if event.key == pygame.K_RETURN:
                                l = self.get_serverlist()
                                self.serverlist_i %= len(l)
                                self.host = l[self.serverlist_i]
                                in_select_server = False
                            elif event.key == pygame.K_ESCAPE:
                                in_select_server = False
                            elif event.key == pygame.K_UP:
                                self.serverlist_i -= 1
                            elif event.key == pygame.K_DOWN:
                                self.serverlist_i += 1
                        else:
                            if event.key == pygame.K_RETURN:
                                self.tron_client.connect(self.host, self.port,
                                                         self.name)
                            elif event.key == pygame.K_TAB:
                                self.edit = (self.edit + 1) % 2
                            elif event.key == pygame.K_f \
                                    and (mods & pygame.KMOD_CTRL):
                                in_select_server = True
                            elif event.key == pygame.K_BACKSPACE:
                                if self.edit == 0:
                                    self.name = self.name[:-1]
                                elif self.edit == 1:
                                    self.host = self.host[:-1]
                            else:
                                char = event.unicode
                                if char.isprintable():
                                    if self.edit == 0:
                                        self.name += char
                                    elif self.edit == 1:
                                        self.host += char
                            
                    elif self.tron_client.game_is_on():
                        keymap = {
                            pygame.K_LEFT: "L",
                            pygame.K_RIGHT: "R",
                            pygame.K_UP: "U",
                            pygame.K_DOWN: "D",
                        }
                        if event.key in keymap:
                            self.tron_client.send_move(keymap[event.key])
                    elif self.tron_client.received_end():
                        self.tron_client.ready_to_end = True
                        self.winner = None
                    elif self.tron_client.received_go():
                        self.tron_client.ready_to_go = True

            pygame.display.flip()
            self.clock.tick(self.fps)

def main(argv):
    tron2d = Tron2D(60, 800, 600)
    tron2d.run()

main(sys.argv)
