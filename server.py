import socket
import argparse
import re
from echo_server import conn, addr

errors = {
    100: 'Unknown command',
    101: 'Malformed or missing arguments (includes an illegal nickname)',
    102: 'Nickname already taken',
    103: 'Command requires a nickname and none is set',
    104: 'No such user', #For PMs
    105: 'Line exceeds 512 bytes'
}

class Client():
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.nickname = ''
        self.buffer = b''

    def print_error(self, e):
        if e in errors:
            print('ERROR:', errors[e])

    def ingest_lines(self):
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk
        
            while b'\n' in buffer:
                raw, buffer = buffer.split(b'\n', 1)
                line = raw.rstrip(b'\r').decode('utf-8', errors='replace').strip()
                if line:
                    self.handle_line(line)

    def handle_line(self, line):
        if len(line.encode('utf-8')) > 512:
            print(errors[105])
            return

        split = line.split()
        if split:
            verb = split[0].upper()
            args = split.copy().remove(verb)

            match verb:
                case 'NICK':
                    self.handle_nick(args)
                case 'MSG':
                    self.handle_msg(args)
                case 'PM':
                    self.handle_pm(args)
                case 'WHO':
                    self.handle_who(args)
                case 'QUIT':
                    self.handle_quit(args)
        else:
            self.print_error(100)

    def handle_nick(self, args):
        if not len(args) == 1 or not re.fullmatch('[A-Za-z0-9_]', args[0]):
            self.print_error(101)
            return

        if args[0] == 'name': # Make this a check if the name is in user list (Server side)
            self.print_error(102)
            return

        self.nickname = args[0]

    def handle_msg(self, args):
        text = args.join()

    def handle_pm(self, args):
        if not len(args) > 1:
            self.print_error(101)
            return

        text = args.copy().remove(args[0]).join()

        if not args[0] == 'name': # Make this a check if the name is in user list (Server side)
            self.print_error(104)
            return

    def handle_who(self, args):
        if not len(args) == 0:
            self.print_error(101)
            return

        print('users') # print user list (Server side)

    def handle_quit(self, args):
        if not len(args) == 0:
            self.print_error(101)
            return

        print('quit') #disconnect from server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5050)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))

    client = Client()

if __name__ == '__main__':
    main()