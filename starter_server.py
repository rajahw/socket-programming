#!/usr/bin/env python3
"""
TuskChat starter -- hand this to students at the start of M2.

The accept loop and the line-buffering loop are written for you, because those
are the two places where a beginner gets stuck for four hours with nothing to
show. Everything marked TODO is yours.

Run:  python3 starter_server.py --port 5050
Test: nc 127.0.0.1 5050
"""

import argparse
import socket
import threading

MAX_LINE = 512

# Shared state. Every thread touches this, so every access needs the lock.
clients = {}                       # nickname -> connection object
clients_lock = threading.Lock()


class Client:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.nick = None
        self.send_lock = threading.Lock()

    def send_line(self, text):
        """Always send through here. sendall() loops over partial writes."""
        with self.send_lock:
            try:
                self.conn.sendall((text + "\n").encode())
            except OSError:
                pass


def handle_line(cli, line):
    """
    Handle one complete command line from one client.

    Return "close" to hang up on this client, or None to keep going.

    TODO (M2): NICK, MSG, WHO, QUIT and the ERR codes from the spec.
    TODO (M3): PM, broadcast to everyone but the sender, INFO notices.
    """
    parts = line.split(" ", 1)
    verb = parts[0].upper()
    rest = parts[1] if len(parts) > 1 else ""

    if verb == "NICK":
        # TODO: validate the nickname, reject duplicates (ERR 102),
        #       register it under clients_lock, reply OK, notify others.
        cli.send_line("ERR 100 unknown command")

    elif verb == "QUIT":
        cli.send_line("OK bye")
        return "close"

    else:
        cli.send_line("ERR 100 unknown command")

    return None


def serve_client(conn, addr):
    """
    One thread per client. The buffering loop below is the part students
    most often get wrong, so it is provided -- read it until you can explain
    why the `while b"\\n" in buf` loop is a `while` and not an `if`.
    """
    cli = Client(conn, addr)
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:                       # empty result == peer closed
                break
            buf += chunk

            while b"\n" in buf:                 # may be several lines at once
                raw, buf = buf.split(b"\n", 1)
                line = raw.rstrip(b"\r").decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if handle_line(cli, line) == "close":
                    return

            if len(buf) > MAX_LINE:             # a line that never ends
                cli.send_line("ERR 105 line too long")
                buf = b""
    except OSError:
        pass
    finally:
        # TODO (M3): remove this client from the roster and send an INFO notice.
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5050)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # do not delete
    srv.bind((args.host, args.port))
    srv.listen(16)
    print(f"listening on {args.host}:{args.port}")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=serve_client, args=(conn, addr),
                             daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


if __name__ == "__main__":
    main()
