import socket
import argparse
import re

ERRORS = {
    100: 'Unknown command',
    101: 'Malformed or missing arguments (includes an illegal nickname)',
    102: 'Nickname already taken',
    103: 'Command requires a nickname and none is set',
    104: 'No such user', #For PMs
    105: 'Line exceeds 512 bytes'
}

class User:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.nickname = None
        self.buffer = b''
        self.active = True
 
    def send_line(self, text):
        data = (text + '\n').encode('utf-8', errors='replace')
        try:
            self.conn.sendall(data)
        except OSError:
            pass
 
    def send_error(self, code):
        self.send_line('ERR ' + str(code) + ' ' + str(ERRORS[code]))

    def send_success(self, verb):
        self.send_line('OK ' + str(verb) + ' SUCCESS')

def ingest_lines(user):
    while user.active:
        chunk = user.conn.recv(4096)
        if not chunk:
            break
        user.buffer += chunk
        
        while b'\n' in user.buffer:
            raw, user.buffer = user.buffer.split(b'\n', 1)
            line = raw.rstrip(b'\r').decode('utf-8', errors='replace').strip()
            if line:
                handle_line(line, user)

def handle_line(line, user):
    if len(line.encode('utf-8')) > 512:
        user.send_error(105)
        return

    split = line.split()
    if split:
        verb = split[0].upper()
        args = split[1:]

        match verb:
            case 'NICK':
                handle_nick(args, user)
            case 'MSG':
                handle_msg(args, user)
            case 'PM':
                handle_pm(args, user)
            case 'WHO':
                handle_who(args, user)
            case 'QUIT':
                handle_quit(args, user)
            case _:
                user.send_error(100)
    else:
        user.send_error(100)

def handle_nick(args, user):
    if not len(args) == 1 or not re.fullmatch('[A-Za-z0-9_]+', args[0]) or not (len(args[0]) > 0 and len(args[0])<= 16):
        user.send_error(101)
        return

    if args[0] == 'name': # Make this a check if the name is in user list (Server side)
        user.send_error(102)
        return

    user.nickname = args[0]

    user.send_success('NICK')

def handle_msg(args, user):
    if user.nickname is None:
        user.send_error(103)
        return

    text = ' '.join(args)

    user.send_success('MSG')

def handle_pm(args, user):
    if not len(args) > 1:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    if not args[0] == 'name': # Make this a check if the name is in user list (Server side)
        user.send_error(104)
        return

    text = ' '.join(args[1:])

    user.send_success('PM')

def handle_who(args, user):
    if not len(args) == 0:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    print('users') # print user list (Server side)

    user.send_success('WHO')

def handle_quit(args, user):
    if not len(args) == 0:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    user.active = False

    user.send_success('QUIT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5050)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(10)

    while True:
        conn, addr = sock.accept()
        user = User(conn, addr)
        print('connected:', addr)
        try:
            ingest_lines(user)
        except (OSError):
            pass
        finally:
            print('disconnected:', addr)
            conn.close()

if __name__ == '__main__':
    main()