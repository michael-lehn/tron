import socket
import select

class TronServer:
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

class TronClient:
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

