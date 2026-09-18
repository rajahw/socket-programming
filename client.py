import socket
import argparse
import re
import threading
import traceback

ERRORS = {
    100: 'Unknown command',
    101: 'Malformed or missing arguments (includes an illegal nickname)',
    102: 'Nickname already taken',
    103: 'Command requires a nickname and none is set',
    104: 'No such user',
    105: 'Line exceeds 512 bytes'
}

users = {}
users_lock = threading.Lock()

class User:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.nickname = None
        self.buffer = b''
        self.active = True
        self.discarding = False
        self.send_lock = threading.Lock()
 
    def send_line(self, text):
        data = (text + '\n').encode('utf-8', errors='replace')
        with self.send_lock:
            try:
                self.conn.sendall(data)
            except OSError:
                pass
 
    def send_error(self, code):
        self.send_line(f'ERR {code} {ERRORS[code]}')

    def send_success(self, verb):
        self.send_line(f'OK {verb} SUCCESS')

def broadcast(text, exclude=None):
    with users_lock:
        recipients = list(users.values())

    for r in recipients:
        if r is not exclude:
            r.send_line(text)

def ingest_lines(user):
    while user.active:
        chunk = user.conn.recv(4096)
        if not chunk:
            break
        user.buffer += chunk

        if user.discarding:
            if b'\n' in user.buffer:
                _, user.buffer = user.buffer.split(b'\n', 1)
                user.discarding = False
            else:
                user.buffer = b''
                continue

        while b'\n' in user.buffer:
            raw, user.buffer = user.buffer.split(b'\n', 1)
            line = raw.rstrip(b'\r').decode('utf-8', errors='replace').strip()
            if line:
                handle_line(line, user)
                if not user.active:
                    return

        if len(user.buffer) > 512:
            user.send_error(105)
            user.buffer = b''
            user.discarding = True

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

    taken = False

    with users_lock:
        if args[0] in users:
            taken = True
        else:
            if user.nickname:
                users.pop(user.nickname, None)

            user.nickname = args[0]

            users[user.nickname] = user

            online = len(users)

    if taken:
        user.send_error(102)
        return

    user.send_success('NICK')

    broadcast(f'INFO {user.nickname} joined. ({online} online)', exclude=user)

def handle_msg(args, user):
    if user.nickname is None:
        user.send_error(103)
        return

    text = ' '.join(args)

    broadcast(f'MSG {user.nickname} {text}', exclude=user)

    user.send_success('MSG')

def handle_pm(args, user):
    if not len(args) > 1:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    if args[0] == user.nickname:
        user.send_error(101)
        return

    with users_lock:
        target = users.get(args[0])

    if target is None:
        user.send_error(104)
        return

    text = ' '.join(args[1:])

    target.send_line(f'PM {user.nickname} {text}')

    user.send_success('PM')

def handle_who(args, user):
    if not len(args) == 0:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    with users_lock:
        nicknames = list(users)

    user_list = ' '.join(nicknames)

    user.send_line(f'USERS {len(nicknames)} {user_list}')

    user.send_success('WHO')

def handle_quit(args, user):
    if not len(args) == 0:
        user.send_error(101)
        return

    if user.nickname is None:
        user.send_error(103)
        return

    with users_lock:
        users.pop(user.nickname, None)

    user.send_success('QUIT')

    user.active = False

def serve_user(conn, addr):
    user = User(conn, addr)
    try:
        ingest_lines(user)
    except Exception:
        traceback.print_exc()
    finally:
        if user.nickname:
            with users_lock:
                users.pop(user.nickname, None)
                online = len(users)
            broadcast(f'INFO {user.nickname} left. ({online} online)')
        conn.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5050)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(10)

    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=serve_user, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()

if __name__ == '__main__':
    main()