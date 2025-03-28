import sys
import math
import random
from tron_network import TronClient

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

PORT = 65432
FPS = 80

ARENA_WIDTH, ARENA_HEIGHT = 1000, 1000
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600

def rgb255(r, g, b):
    return (r / 255.0, g / 255.0, b / 255.0)

def rgba255(r, g, b, a):
    return (r / 255.0, g / 255.0, b / 255.0, a)

C_PLAYER = [ rgba255(0, 255, 255, 1), # cyan
             rgba255(255, 100, 0, 1)  # orange
           ]

C_WALL = [ rgba255(0, 255, 255, 0.5),
           rgba255(255, 100, 0, 0.5)
         ]

C_BLACK = rgb255(0, 0, 0)
C_ARENA = rgb255(50, 50, 50)
C_GRID = rgb255(200, 200, 200)

GRID_Z = 1
CYCLE_Z = 10

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

def set_camera(x, y, dx, dy, cam_z):
    target_x = x + dx * 20
    target_y = y + dy * 20
    target_z = cam_z

    gluLookAt(x, y, cam_z,
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


class ArenaViewer:

    def __init__(self, width, height):
        pygame.init()
        self.width = width
        self.height = height
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        self.i_am = None
        self.new_round()

        pygame.display.set_caption("TRON Client with OpenGL")
        self.clock = pygame.time.Clock()

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
        gluPerspective(45, width / height, 0.1, 2000.0)

        # Generate display list for arena and grid
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.grid_list_id = glGenLists(1)
        glNewList(self.grid_list_id, GL_COMPILE)
        self._build_grid()
        glEndList()

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

        # Setup light
        setup_directional_light(GL_LIGHT0, (1.0, 0.0, -1.0))
        setup_directional_light(GL_LIGHT1, (-1.0, 0.0, 1.0))
        setup_directional_light(GL_LIGHT2, (1.0, 0.0, 1.0))
        setup_directional_light(GL_LIGHT3, (-1.0, 0.0, -1.0))

    def __del__(self):
        pygame.quit()

    def new_round(self):
        self.player = []
        self.i_am_alive = True

    def add_player(self, p):
        p.player_index = len(self.player)
        self.player.append(p)

    def del_player(self, player_index):
        if self.i_am == player_index:
            self.i_am_alive = False
        self.player[player_index].alive = False

    def set_position(self, pos_list):
        for i, p in enumerate(self.player):
            if p is not None:
                p.set_position(pos_list[2*i], pos_list[2*i + 1])

    def set_i_am_player(self, index):
        self.i_am = index

    def i_am_player(self):
        if self.i_am is not None \
                and self.i_am < len(self.player) \
                and self.player[self.i_am]:
            return  self.player[self.i_am]
        else:
            return None

    def _build_grid(self):
        glEnable(GL_POLYGON_OFFSET_FILL)
        glPolygonOffset(1.0, 1.0)

        tile_size = 50

        glColor3f(*C_ARENA)
        glNormal3f(0.0, 0.0, 1.0)
        for x in range(0, ARENA_WIDTH, tile_size):
            for y in range(0, ARENA_HEIGHT, tile_size):
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
        for x in range(0, ARENA_WIDTH + 1, tile_size):
            glVertex3f(x, 0, GRID_Z)
            glVertex3f(x, ARENA_HEIGHT, GRID_Z)

        for y in range(0, ARENA_HEIGHT + 1, tile_size):
            glVertex3f(0, y, GRID_Z)
            glVertex3f(ARENA_WIDTH, y, GRID_Z)
        glEnd()

        glEnable(GL_LIGHTING)  # Re-enable lighting after drawing lines

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

        self.draw_frame()

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
        skew = 40

        x0 = pad_x if side == 0 else SCREEN_WIDTH - w - pad_x
        y0 = pad_y

        skew_sign = 1 if side == 0 else -1

        glColor3f(1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x0, y0 + skew_sign * 0)
        glTexCoord2f(1, 0); glVertex2f(x0 + w, y0)
        glTexCoord2f(1, 1); glVertex2f(x0 + w, y0 + h)
        glTexCoord2f(0, 1); glVertex2f(x0, y0 + h + skew_sign * skew)
        glEnd()

        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def draw_minimap(self):
        if (p := self.i_am_player()) and p.x is not None and p.y is not None:
            mm_width, mm_height = 200, 150
            view_width, view_height = SCREEN_WIDTH, SCREEN_HEIGHT

            x0, y0 = (SCREEN_WIDTH - mm_width) // 2, 20
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
            glVertex2f(0, ARENA_HEIGHT)
            glVertex2f(ARENA_WIDTH, ARENA_HEIGHT)
            glVertex2f(ARENA_WIDTH, 0)
            glEnd()

            # Jetwall
            for i, p in enumerate(self.player):
                if p.alive:
                    glColor4f(*C_PLAYER[i])
                    glBegin(GL_LINE_STRIP)
                    for a, b in p.path:
                        glVertex2f(a, b)
                    glEnd()

            # Players
            for i, p in enumerate(self.player):
                if p.alive:
                    glColor4f(*C_PLAYER[i])
                    glPointSize(5)
                    glBegin(GL_POINTS)
                    glVertex2f(p.x, p.y)
                    glEnd()

            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
    

    def set_camera(self, look = 0):
        if (p := self.i_am_player()):
            p.set_camera(look)

    def draw_frame(self):
        glCallList(self.grid_list_id)
        for i, p in enumerate(self.player):
            if p.alive:
                p.draw_cycle()
        for i, p in enumerate(self.player):
            if p.alive:
                p.draw_wall()

    def next_frame(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.render_side_camera_to_texture(0)
        self.render_side_camera_to_texture(1)
        glViewport(0, 0, self.width, self.height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, self.width / self.height, 0.1, 2000.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # forward view
        self.set_camera()
        self.draw_frame()
        self.draw_side_view(0)
        self.draw_side_view(1)
        self.draw_minimap()

        pygame.display.flip()
        self.clock.tick(FPS)

class PlayerViewer:

    def __init__(self):
        self.player_index = None
        self.path = []
        self.dx, self.dy = 0, 0
        self.vx, self.vy = 0, 0
        self.angle = 0
        self.angle_turn = 0
        self.x, self.y = None, None
        self.alive = True


    def draw_wall(self):
        for i in range(len(self.path)-1):
            x0, y0 = self.path[i]
            x1, y1 = self.path[i + 1]
            draw_lightwall(x0, y0, x1, y1, C_WALL[self.player_index])

    def draw_cycle(self):
        if self.x is None or self.y is None:
            return
        if self.dx != 0 or self.dy != 0:
            draw_lightcycle(self.x, self.y, self.dx, self.dy,
                            C_PLAYER[self.player_index])

    def set_camera(self, look = 0):
        if self.x and self.y and (self.vx != 0 or self.vy != 0):
            if look == -1:
                set_camera(self.x, self.y, -self.vy, self.vx, 25)
            elif look == 1:
                set_camera(self.x, self.y, self.vy, -self.vx, 25)
            else:
                set_camera(self.x, self.y, self.vx, self.vy, 25)

    def set_position(self, x, y):
        self.x, self.y = x, y
        if len(self.path) == 0:
            self.path = [ (self.x, self.y) ]
        last_x, last_y = self.path[-1]
        vx, vy = self.x - last_x, self.y - last_y
        dx, dy = sign(vx), sign(vy)

        if dx == 0 and dy == 0:
            return

        if dx == self.dx and dy == self.dy:
            self.path[-1] = (self.x, self.y)
        else:
            self.path.append((self.x, self.y))
            self.dx, self.dy = dx, dy
            self.vx, self.vy = vx, vy

def main(argv):
    if len(argv) != 2:
        print(f"Usage: python {sys.argv[0]} <server-ip>")
        sys.exit(1)
    SERVER_IP = argv[1]

    tronClient = TronClient(SERVER_IP, PORT)
    arenaViewer = ArenaViewer(SCREEN_WIDTH, SCREEN_HEIGHT)

    playing = True
    while playing:
        for event in pygame.event.get():
            if event.type == QUIT:
                playing = False
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    playing = False
                elif event.key == pygame.K_q:
                    playing = False
                elif event.key == pygame.K_i:
                    arenaViewer.set_i_am_player(1 - arenaViewer.i_am)
                else:
                    keymap = {
                        pygame.K_LEFT: "R",
                        pygame.K_RIGHT: "L",
                        pygame.K_UP: "U",
                        pygame.K_DOWN: "D",
                        pygame.K_q: "Q"
                    }
                    if event.key in keymap:
                        cmd = keymap[event.key]
                        if cmd == "Q":
                            tronClient.send("Q")
                            return
                        else:
                            if not tronClient.send(cmd):
                                return
                    
        got = tronClient.read()

        if got is None or got[0] == "Q":
            return False
        elif got[0] == "I":
            print(f"I am Player {got[1]}")
            arenaViewer.set_i_am_player(got[1])
        elif got[0] == "P":
            arenaViewer.set_position(got[1:])
        elif got[0] == "S":
            arenaViewer.new_round()
            arenaViewer.add_player(PlayerViewer())
            arenaViewer.add_player(PlayerViewer())
        elif got[0] == "D":
            arenaViewer.del_player(got[1])
            print(f"Player {got[1]} is deleted")
        elif got[0] == "E":
            print("Round ended")
        arenaViewer.next_frame()

main(sys.argv)

