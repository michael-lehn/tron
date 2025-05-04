import math
import pygame
import serial
import serial.tools.list_ports
import sys
import getpass

from OpenGL.GL import *
from OpenGL.GLU import *
from enum import Enum, auto
from pygame.locals import *
from tron_client import ServerScanner
from tron_client import TronClient

C_PLAYER = [
    (111, 226, 226), # cyan (Player 1)
    (242, 160, 7),   # orange (Player 2)
    (180, 0, 255),   # neon purple (Player 3)
    (0, 255, 128)    # turquoise green (Player 4)
]

def rgb255(r, g, b):
    return (r / 255.0, g / 255.0, b / 255.0)

def rgba255(r, g, b, a):
    return (r / 255.0, g / 255.0, b / 255.0, a)

C_PLAYER = [
    rgba255(111, 226, 226, 1), # cyan
    rgba255(242, 160,   7, 1), # orange
    rgba255(180,   0, 255, 1), # neon purple
    rgba255(  0, 255, 128, 1)  # turquoise green
]

C_WALL = [
    rgba255(  0, 255, 255, 0.5),
    rgba255(255, 100,   0, 0.5),
    rgba255(180,   0, 255, 0.5),
    rgba255(  0, 255, 128, 0.5)
]

C_BLACK = rgb255(0, 0, 0)
C_ARENA = rgb255(50, 50, 50)
C_GRID = rgb255(200, 200, 200)

GRID_Z = 1
CYCLE_Z = 10

def set_camera(x, y, dx, dy, cam_z, look = 0):
    if look == -1:
        dx, dy = -dy, dx
    elif look == 1:
        dx, dy = dy, -dx

    target_x = x + dx * 10000
    target_y = y + dy * 10000
    target_z = cam_z

    gluLookAt(
            x, y, cam_z,
            target_x, target_y, target_z,
              0, 0, 1)

def setup_directional_light(light_id=GL_LIGHT0,
                             light_direction = (0.0, -1.0, -1.0),
                             ambient = (0.4, 0.4, 0.4, 1.0),
                             diffuse = (0.3, 0.3, 0.3, 1.0),
                             specular = (1.0, 1.0, 1.0, 1.0)):

    glEnable(GL_LIGHTING)
    glEnable(light_id)

    glLightfv(light_id, GL_POSITION, light_direction)
    glLightfv(light_id, GL_AMBIENT, ambient)
    glLightfv(light_id, GL_DIFFUSE, diffuse)
    glLightfv(light_id, GL_SPECULAR, specular)

    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (1.0, 1.0, 1.0, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 80.0)

def draw_lightwall(x0, y0, x1, y1, color, height=90, thickness=4):
    dx = x1 - x0
    dy = y1 - y0
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        return

    dx /= length
    dy /= length

    nx = -dy * thickness / 2
    ny = dx * thickness / 2

    z0 = GRID_Z + 10 
    z1 = z0 + height

    glColor4f(*color)

    glBegin(GL_QUADS)

    # Right side when viewed from the front
    glNormal3f(dx, dy, 0.0)
    glVertex3f(x0 + nx, y0 + ny, z0)
    glVertex3f(x1 + nx, y1 + ny, z0)
    glVertex3f(x1 + nx, y1 + ny, z1)
    glVertex3f(x0 + nx, y0 + ny, z1)

    # Left side when viewed from the front
    glNormal3f(-dx, -dy, 0.0)
    glVertex3f(x1 - nx, y1 - ny, z0)
    glVertex3f(x0 - nx, y0 - ny, z0)
    glVertex3f(x0 - nx, y0 - ny, z1)
    glVertex3f(x1 - nx, y1 - ny, z1)

    # Back when viewed from the back
    glNormal3f(-dy, dx, 0.0)
    glVertex3f(x0 - nx, y0 - ny, z1)
    glVertex3f(x0 + nx, y0 + ny, z1)
    glVertex3f(x0 + nx, y0 + ny, z0)
    glVertex3f(x0 - nx, y0 - ny, z0)

    # Front side when viewed from the front
    glNormal3f(dy, -dx, 0.0)
    glVertex3f(x1 + nx, y1 + ny, z1)
    glVertex3f(x1 - nx, y1 - ny, z1)
    glVertex3f(x1 - nx, y1 - ny, z0)
    glVertex3f(x1 + nx, y1 + ny, z0)

    # Top
    glNormal3f(0.0, 0.0, 1.0)
    glVertex3f(x0 - nx, y0 - ny, z1)
    glVertex3f(x0 + nx, y0 + ny, z1)
    glVertex3f(x1 + nx, y1 + ny, z1)
    glVertex3f(x1 - nx, y1 - ny, z1)

    # Bottom
    glNormal3f(0.0, 0.0, -1.0)
    glVertex3f(x1 - nx, y1 - ny, z0)
    glVertex3f(x1 + nx, y1 + ny, z0)
    glVertex3f(x0 + nx, y0 + ny, z0)
    glVertex3f(x0 - nx, y0 - ny, z0)

    glEnd()

def draw_lightcycle(x, y, dx, dy, color):
    glPushMatrix()

    CYCLE_WIDTH  = 20
    CYCLE_LENGTH = 40
    CYCLE_HEIGHT = 20

    # Position and orientation
    glTranslatef(x, y, CYCLE_Z)
    angle = math.degrees(math.atan2(-dx, dy))
    glRotatef(angle, 0, 0, 1)

    w0 = CYCLE_WIDTH / 2
    w1 = w0 / 2
    l = CYCLE_LENGTH / 2
    h0 = CYCLE_HEIGHT
    h1 = h0 / 3

    glBegin(GL_QUADS)
    glColor4f(*color)

    # Bottom
    glNormal3f(0.0, 0.0, 1.0)
    glVertex3f(-w1,  l, 0)
    glVertex3f( w1,  l, 0)
    glVertex3f( w0, -l, 0)
    glVertex3f(-w0, -l, 0)

    # Top
    glNormal3f(-0.0, 0.316, 0.949)  # ≈ 18.43° Neigung nach vorne
    glVertex3f(-w0, -l, h0)
    glVertex3f( w0, -l, h0)
    glVertex3f( w1,  l, h1)
    glVertex3f(-w1,  l, h1)

    # Left
    glNormal3f(0.992, -0.124, 0.0)  # leicht nach innen geneigt
    glVertex3f(-w0, -l, h0)
    glVertex3f(-w1,  l, h1)
    glVertex3f(-w1,  l, 0)
    glVertex3f(-w0, -l, 0)

    # Right
    glNormal3f(0.992, 0.124, 0.0)  # leicht nach innen geneigt
    glVertex3f( w0, -l, 0)
    glVertex3f( w1,  l, 0)
    glVertex3f( w1,  l, h1)
    glVertex3f( w0, -l, h0)

    # Back
    glNormal3f(0.0, -1.0, 0.0)
    glVertex3f(-w0, -l, 0)
    glVertex3f( w0, -l, 0)
    glVertex3f( w0, -l, h0)
    glVertex3f(-w0, -l, h0)

    # Front
    glNormal3f(0.0, -1.0, 0.0)  # bleibt gleich wegen senkrechter Fläche
    glVertex3f(-w1, l, h1)
    glVertex3f( w1, l, h1)
    glVertex3f( w1, l, 0)
    glVertex3f(-w1, l, 0)

    glEnd()
    glPopMatrix()

def _build_grid(width, height):
    glEnable(GL_POLYGON_OFFSET_FILL)
    glPolygonOffset(1.0, 1.0)

    tile_size = 50

    glColor3f(*C_ARENA)
    glNormal3f(0.0, 0.0, 1.0)
    for x in range(0, width, tile_size):
        for y in range(0, height, tile_size):
            glBegin(GL_QUADS)
            glVertex3f(x, y, 0)
            glVertex3f(x + tile_size, y, 0)
            glVertex3f(x + tile_size, y + tile_size, 0)
            glVertex3f(x, y + tile_size, 0)
            glEnd()

    glDisable(GL_LIGHTING)
    glColor3f(*C_GRID)
    glLineWidth(2.5)

    glBegin(GL_LINES)
    for x in range(0, width + 1, tile_size):
        glVertex3f(x, 0, GRID_Z)
        glVertex3f(x, height, GRID_Z)

    for y in range(0, height + 1, tile_size):
        glVertex3f(0, y, GRID_Z)
        glVertex3f(width, y, GRID_Z)
    glEnd()

    glEnable(GL_LIGHTING)  # !!! Re-enable lighting after drawing lines

def open_serial():
    ser_dev = next(
        (p.device for p in serial.tools.list_ports.comports()
            if p.device.startswith("/dev/cu.usbserial")),
        None
    )
    try:
        ser = serial.Serial(ser_dev, 9600, timeout=0)
        ser.write(b'X')
        return ser
    except:
        print(f"can not open serial device {ser_dev}")
    return None

class Tron3D:

    class Mode(Enum):
        IN_2D = auto()
        IN_3D = auto()

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

        self.tron_client = TronClient(self)

        pygame.init()
        pygame.display.set_caption("TRON: Lightcycle 3D")

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

        self.mode = None
        self.look = 0
        self.clock = pygame.time.Clock()

    def __del__(self):
        pygame.quit()

    def set_mode(self, mode):
        if self.mode == mode:
            return
        self.mode = mode
        if mode == Tron3D.Mode.IN_2D:
            self.init_2d()
        elif mode == Tron3D.Mode.IN_3D:
            self.init_3d()

    def init_2d(self):
        self.screen = pygame.display.set_mode((self.width, self.height))

    def init_3d(self):
        arena = self.tron_client.arena
        assert arena is not None

        pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        glClearColor(*C_BLACK, 1.0)

        # Set up perspective
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, self.width / self.height, 0.1, 2000.0)

        # Get id for display list for arena and grid
        self.grid_list_id = glGenLists(1)

        # Textures for left and right view
        self.sideview_tex_size = 512
        self.sideview_fbo = glGenFramebuffers(2)
        self.sideview_tex = glGenTextures(2)
        self.sideview_depth_rb = glGenRenderbuffers(2)

        for i in range(2):
            glBindTexture(GL_TEXTURE_2D, self.sideview_tex[i])
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB,
                         self.sideview_tex_size, self.sideview_tex_size, 0,
                         GL_RGB, GL_UNSIGNED_BYTE, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            glBindFramebuffer(GL_FRAMEBUFFER, self.sideview_fbo[i])
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                   GL_TEXTURE_2D, self.sideview_tex[i], 0)

            glBindRenderbuffer(GL_RENDERBUFFER, self.sideview_depth_rb[i])
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT,
                                  self.sideview_tex_size,
                                  self.sideview_tex_size)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                      GL_RENDERBUFFER,
                                      self.sideview_depth_rb[i])
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        # Setup light
        setup_directional_light(GL_LIGHT0, (1.0, 0.0, -1.0))
        setup_directional_light(GL_LIGHT1, (-1.0, 0.0, 1.0))
        setup_directional_light(GL_LIGHT2, (1.0, 0.0, 1.0))
        setup_directional_light(GL_LIGHT3, (-1.0, 0.0, -1.0))

    def new_arena(self):
        assert self.mode == Tron3D.Mode.IN_3D
        assert self.tron_client.arena is not None
        arena = self.tron_client.arena
        print("new arena")

        # Generate display list for arena and grid
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glNewList(self.grid_list_id, GL_COMPILE)
        _build_grid(arena.width, arena.height)
        glEndList()

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
        self.set_mode(Tron3D.Mode.IN_2D)
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
        self.set_mode(Tron3D.Mode.IN_2D)

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
        self.set_mode(Tron3D.Mode.IN_2D)

        state = self.tron_client.get_state_msg()
        state_text = self.state_font.render(state, True, (150, 150, 150))
        state_rect = state_text.get_rect(center=(self.width // 2,
                                                 self.height - 40))
        self.screen.blit(state_text, state_rect)
        
    def show_score(self):
        self.set_mode(Tron3D.Mode.IN_2D)

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

    def draw_state_overlay(self):
        state = self.tron_client.get_state_msg()
        if not state:
            return

        surface = self.state_font.render(state, True, (200, 200, 200))
        text_data = pygame.image.tostring(surface, "RGBA", True)
        tw, th = surface.get_width(), surface.get_height()

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA,
                     GL_UNSIGNED_BYTE, text_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

        x = (self.width - tw) // 2
        y = 20
        glColor3f(1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, y)
        glTexCoord2f(1, 0); glVertex2f(x + tw, y)
        glTexCoord2f(1, 1); glVertex2f(x + tw, y + th)
        glTexCoord2f(0, 1); glVertex2f(x, y + th)
        glEnd()

        glDeleteTextures([tex_id])
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
    

    def draw_score_overlay(self):
        arena = self.tron_client.arena
        if arena is None or arena.player is None:
            return

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        y = self.height - 30
        for i, p in enumerate(arena.player):
            text = f"{arena.name[i]}: {arena.score[i]}"
            color = tuple(int(c * 255) for c in C_PLAYER[i][:3])
            surface = self.score_font.render(text, True, color)

            text_data = pygame.image.tostring(surface, "RGBA", True)
            tw, th = surface.get_width(), surface.get_height()

            glEnable(GL_TEXTURE_2D)
            tex_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA,
                         GL_UNSIGNED_BYTE, text_data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

            glColor3f(1, 1, 1)
            x, y0 = 10, y
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex2f(x, y0)
            glTexCoord2f(1, 0); glVertex2f(x + tw, y0)
            glTexCoord2f(1, 1); glVertex2f(x + tw, y0 + th)
            glTexCoord2f(0, 1); glVertex2f(x, y0 + th)
            glEnd()

            glDeleteTextures([tex_id])
            glDisable(GL_TEXTURE_2D)
            y -= th + 10

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def show_minimap(self):
        assert self.tron_client.arena is not None
        arena = self.tron_client.arena

        if arena.I_am_player is None or arena.player is None:
            return
        p = arena.player[arena.I_am_player]
        if p is None or p.x is None:
            return

        mm_width, mm_height = 200, 150
        view_width, view_height = self.width, self.height

        x0, y0 = (view_width - mm_width) // 2, 20
        glViewport(x0, y0, mm_width, mm_height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        half_width, half_height = view_width // 2, view_height // 2
        gluOrtho2D(p.x - half_width, p.x + half_width,
                   p.y - half_height, p.y + half_height)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        # Background
        glColor3f(0.2, 0.2, 0.2)
        glBegin(GL_QUADS)
        glVertex2f(p.x - half_width, p.y - half_height)
        glVertex2f(p.x + half_width, p.y - half_height)
        glVertex2f(p.x + half_width, p.y + half_height)
        glVertex2f(p.x - half_width, p.y + half_height)
        glEnd()

        if p.dx != 0 or p.dy != 0:
            glTranslatef(p.x, p.y, 0)
            angle = -math.degrees(math.atan2(p.dx, p.dy))
            glRotatef(-angle, 0, 0, 1)
            glTranslatef(-p.x, -p.y, 0)

        # Arena border
        glColor3f(1, 0, 0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(0, 0)
        glVertex2f(0, arena.width)
        glVertex2f(arena.width, arena.height)
        glVertex2f(arena.width, 0)
        glEnd()

        # Jetwall
        for pi, p in enumerate(arena.player):
            if p is None or p.path is None:
                continue
            glColor4f(*C_PLAYER[pi])
            glBegin(GL_LINE_STRIP)
            for a, b in p.path:
                glVertex2f(a, b)
            glEnd()

        # Players
        for i, p in enumerate(arena.player):
            if p is None or p.path is None:
                continue
            glColor4f(*C_PLAYER[pi])
            glPointSize(5)
            glBegin(GL_POINTS)
            glVertex2f(p.x, p.y)
            glEnd()

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glViewport(0, 0, self.width, self.height)

    def set_camera(self, look = None):
        assert self.tron_client.arena is not None
        arena = self.tron_client.arena

        if look == None:
            look = self.look

        if arena.I_am_player is not None \
                and arena.player[arena.I_am_player] is not None \
                and arena.player[arena.I_am_player].x is not None:
            x = arena.player[arena.I_am_player].x
            y = arena.player[arena.I_am_player].y
            dx = arena.player[arena.I_am_player].dx
            dy = arena.player[arena.I_am_player].dy
            set_camera(x, y, dx, dy, 25, look)
        else:
            set_camera(-10, -10, 1, 1, 25, look)

    def render_side_camera_to_texture(self, side):
        glBindFramebuffer(GL_FRAMEBUFFER, self.sideview_fbo[side])
        glViewport(0, 0, self.sideview_tex_size, self.sideview_tex_size)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, 1.0, 0.1, 2000.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        if side == 0:
            self.set_camera(-1)
        else:
            self.set_camera(1)

        self.draw_frame_3d()

        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def draw_side_view(self, side):
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.sideview_tex[side])

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, self.width, 0, self.height)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        w, h = 200, 200
        pad_x, pad_y = 20, 20
        skew = 20

        x0 = pad_x if side == 0 else self.width - w - pad_x
        y0 = pad_y

        skew_x = skew if side == 0 else -skew

        glColor3f(1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x0 + skew_x, y0)
        glTexCoord2f(1, 0); glVertex2f(x0 + w + skew_x, y0)
        glTexCoord2f(1, 1); glVertex2f(x0 + w - skew_x, y0 + h)
        glTexCoord2f(0, 1); glVertex2f(x0 - skew_x, y0 + h)
        glEnd()

        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def show_arena_3d(self):
        self.set_mode(Tron3D.Mode.IN_3D)
        assert self.tron_client.arena is not None
        arena = self.tron_client.arena

        if arena.width == None:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.render_side_camera_to_texture(0)
        self.render_side_camera_to_texture(1)
        glViewport(0, 0, self.width, self.height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, arena.width / arena.height, 0.1, 2000.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        self.set_camera()
        self.draw_frame_3d()
        self.draw_side_view(0)
        self.draw_side_view(1)

    def draw_frame_3d(self):
        assert self.tron_client.arena is not None
        arena = self.tron_client.arena

        glCallList(self.grid_list_id)

        for pi, p in enumerate(arena.player):
            if p is None or p.path is None:
                continue
            draw_lightcycle(p.x, p.y, p.dx, p.dy, C_PLAYER[pi])
            for i in range(len(p.path) - 1):
                x0, y0 = p.path[i]
                x1, y1 = p.path[i + 1]
                draw_lightwall(x0, y0, x1, y1, C_WALL[pi])

    def run(self):
        in_select_server = False
        while True:
            self.tron_client.run()
            if self.mode == Tron3D.Mode.IN_2D or self.tron_client.arena is None:
                self.screen.fill((0, 0, 0))

            if self.tron_client.not_connected():
                if in_select_server:
                    self.show_serverlist()
                    self.show_state()
                else:
                    self.show_connect()
                    self.show_state()
            else:
                self.show_arena_3d()
                self.show_minimap()
                self.draw_score_overlay()
                self.draw_state_overlay()

            try:
                if self.ser is not None and self.ser.in_waiting > 0:
                    ch = self.ser.read(1)
                    print(f"get form serial {ch}")
                    if ch == b"A" or ch == b"R":
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("L")
                        elif self.tron_client.received_end():
                            self.tron_client.ready_to_end = True
                            self.winner = None
                        elif self.tron_client.received_go():
                            self.tron_client.ready_to_go = True
                    elif ch == b"B" or ch == b"L":
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("R")
                    elif ch == b"U":
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("U")
                    elif ch == b"D":
                        if self.tron_client.game_is_on():
                            self.tron_client.send_move("D")
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
            except:
                self.ser = None

            for event in pygame.event.get():
                mods = pygame.key.get_mods()
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q and (mods & pygame.KMOD_CTRL):
                        return
                    elif event.key == pygame.K_p and (mods & pygame.KMOD_CTRL):
                        self.ser = open_serial()
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
                            pygame.K_LEFT: "R",
                            pygame.K_RIGHT: "L",
                            pygame.K_UP: "U",
                            pygame.K_DOWN: "D",
                        }
                        if event.key in keymap:
                            self.tron_client.send_move(keymap[event.key])
                        elif event.key == pygame.K_a:
                            self.look = -1
                        elif event.key == pygame.K_s:
                            self.look = 0
                        elif event.key == pygame.K_d:
                            self.look = 1
                    elif self.tron_client.received_end():
                        self.tron_client.ready_to_end = True
                        self.winner = None
                    elif self.tron_client.received_go():
                        self.tron_client.ready_to_go = True

            pygame.display.flip()
            self.clock.tick(self.fps)

def main(argv):
    tron3d = Tron3D(60, 800, 600)
    tron3d.run()

main(sys.argv)
