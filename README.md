# TRON – A Networked Lightcycle Game in Python

This is a multiplayer TRON-style lightcycle game implemented in Python. It
includes a game server and two client options: a simple 2D client and a 3D
OpenGL-based client. Two players connect to the server and race in a
rectangular arena, leaving trails behind as they move.

## Requirements

You will need the following Python packages:

- `PyOpenGL`
- `PyOpenGL_accelerate`
- `pygame`
- `numpy`
- `pyserial`

## Installation

### On macOS

Use the following command on macOS:

```bash
pip install --break-system-packages --user PyOpenGL PyOpenGL_accelerate pygame numpy pyserial
```

> Note: The `--break-system-packages` flag is required on macOS to allow
> installing packages outside the system-managed environment.

### On Linux or Windows

Use this command on Linux or Windows:

```bash
pip install --user PyOpenGL PyOpenGL_accelerate pygame numpy pyserial
```

> Alternatively, you can create a virtual environment:
>
> ```bash
> python -m venv tron-env
> source tron-env/bin/activate  # On Windows: tron-env\Scripts\activate
> pip install PyOpenGL PyOpenGL_accelerate pygame numpy pyserial
> ```

## Running the Server

To start the game server, run:

```bash
python new-tron-server.py 1000 1000 2
```

This starts a 1000 × 1000 arena for two players.

## Running a Client

You can choose between a 2D or 3D client.

### 2D Client

To start the 2D client:

```bash
python tron-2d.py
```

### 3D Client

To start the 3D client:

```bash
python tron-3d.py
```

In both cases, you will be prompted to enter your **player name** and the **IP
address** of the server.

## Controls

Use the arrow keys to control your lightcycle:

- ⬅️ Left Arrow — Turn left  
- ➡️ Right Arrow — Turn right  
- ⬆️ Up Arrow — Accelerate  
- ⬇️ Down Arrow — Decelerate

## License

This project is provided for educational and non-commercial use.

