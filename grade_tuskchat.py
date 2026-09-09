#!/usr/bin/env python3
"""
TuskChat black-box grader.

Starts nothing itself -- point it at an already-running student server:

    python3 solution_reference.py --port 5050 &
    python3 grade_tuskchat.py --host 127.0.0.1 --port 5050

Exercises the protocol over real sockets, including the failure modes
students usually miss (partial writes, no trailing newline, dead peers,
oversized lines). Prints a per-test result and a suggested M2/M3/M4 score.

Every test uses raw sockets, never the student's client, so a broken
client cannot mask a working server or vice versa.
"""

import argparse
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 5050
TIMEOUT = 3.0

results = []


class Peer:
    """A raw socket with line buffering -- what netcat gives you, in code."""

    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
        self.s.settimeout(TIMEOUT)
        self.buf = b""

    def send(self, text, newline=True):
        self.s.sendall(text.encode() + (b"\n" if newline else b""))

    def send_raw(self, data):
        self.s.sendall(data)

    def line(self, timeout=TIMEOUT):
        """Read one protocol line, or None on timeout/close."""
        self.s.settimeout(timeout)
        while b"\n" not in self.buf:
            try:
                chunk = self.s.recv(4096)
            except (socket.timeout, TimeoutError):
                return None
            except OSError:
                return None
            if not chunk:
                return None
            self.buf += chunk
        raw, self.buf = self.buf.split(b"\n", 1)
        return raw.rstrip(b"\r").decode(errors="replace")

    def lines_until(self, prefix, limit=8, timeout=TIMEOUT):
        """Skip INFO chatter and return the first line starting with prefix."""
        for _ in range(limit):
            ln = self.line(timeout)
            if ln is None:
                return None
            if ln.startswith(prefix):
                return ln
        return None

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass

    def kill(self):
        """Abortive close -- simulates a client that crashed mid-session."""
        try:
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                              b"\x01\x00\x00\x00\x00\x00\x00\x00")
            self.s.close()
        except OSError:
            pass


def check(name, milestone, fn):
    try:
        ok, detail = fn()
    except Exception as e:                      # a crash is a failure, not a stop
        ok, detail = False, f"{type(e).__name__}: {e}"
    results.append((milestone, name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -- {detail}" if detail and not ok else ""))


# ---------------------------------------------------------------- M2 tests --
def t_nick_ok():
    p = Peer()
    p.send("NICK ada")
    r = p.line()
    p.close()
    return (r is not None and r.startswith("OK")), f"got {r!r}"


def t_unknown_command():
    p = Peer()
    p.send("NICK ada")
    p.line()
    p.send("FLY high")
    r = p.lines_until("ERR")
    p.close()
    return (r is not None and r.startswith("ERR 100")), f"got {r!r}"


def t_msg_before_nick():
    p = Peer()
    p.send("MSG hello")
    r = p.lines_until("ERR")
    p.close()
    return (r is not None and r.startswith("ERR 103")), f"got {r!r}"


def t_bad_nick():
    p = Peer()
    p.send("NICK this_nickname_is_far_too_long_to_be_legal")
    r = p.lines_until("ERR")
    p.close()
    return (r is not None and r.startswith("ERR 101")), f"got {r!r}"


def t_split_line():
    """The framing test: one logical line delivered in three TCP writes."""
    p = Peer()
    p.send_raw(b"NI")
    time.sleep(0.15)
    p.send_raw(b"CK sp")
    time.sleep(0.15)
    p.send_raw(b"lit\n")
    r = p.line()
    p.close()
    return (r is not None and r.startswith("OK")), f"got {r!r}"


def t_two_lines_one_write():
    """The other half of framing: two logical lines in a single TCP write."""
    p = Peer()
    p.send_raw(b"NICK glued\nWHO\n")
    first = p.line()
    second = p.lines_until("USERS")
    p.close()
    return (first is not None and first.startswith("OK") and second is not None), \
           f"got {first!r} then {second!r}"


def t_no_trailing_newline():
    """A half-line must not be executed and must not hang the server."""
    p = Peer()
    p.send_raw(b"NICK dangling")          # no \n
    stray = p.line(timeout=1.0)
    p.send_raw(b"\n")
    r = p.line()
    p.close()
    return (stray is None and r is not None and r.startswith("OK")), \
           f"premature={stray!r} then {r!r}"


def t_oversized_line():
    p = Peer()
    p.send("NICK bigmouth")
    p.line()
    p.send("MSG " + "z" * 900)
    r = p.lines_until("ERR", timeout=2.0)
    ok = r is not None and r.startswith("ERR 105")
    if not ok:                            # tolerate silent-drop, reject a crash
        p.send("WHO")
        alive = p.lines_until("USERS", timeout=2.0)
        p.close()
        return (alive is not None), f"no ERR 105 and server unresponsive after"
    p.close()
    return True, ""


# ---------------------------------------------------------------- M3 tests --
def t_broadcast():
    a, b = Peer(), Peer()
    a.send("NICK alice"); a.line()
    b.send("NICK bob");   b.line()
    a.send("MSG hello everyone")
    got = b.lines_until("MSG ")
    a.close(); b.close()
    return (got is not None and "hello everyone" in got and "alice" in got), f"got {got!r}"


def t_no_echo_to_sender():
    a, b = Peer(), Peer()
    a.send("NICK carol"); a.line()
    b.send("NICK dave");  b.line()
    a.send("MSG solo")
    a.lines_until("OK", timeout=1.0)
    leaked = a.lines_until("MSG carol", limit=3, timeout=1.0)
    b.lines_until("MSG ")
    a.close(); b.close()
    return (leaked is None), "sender received its own broadcast"


def t_duplicate_nick():
    a, b = Peer(), Peer()
    a.send("NICK eve"); a.line()
    b.send("NICK eve")
    r = b.lines_until("ERR")
    a.close(); b.close()
    return (r is not None and r.startswith("ERR 102")), f"got {r!r}"


def t_who():
    a, b = Peer(), Peer()
    a.send("NICK frank"); a.line()
    b.send("NICK grace"); b.line()
    a.send("WHO")
    r = a.lines_until("USERS")
    a.close(); b.close()
    return (r is not None and "frank" in r and "grace" in r), f"got {r!r}"


def t_private_message():
    a, b, c = Peer(), Peer(), Peer()
    a.send("NICK heidi"); a.line()
    b.send("NICK ivan");  b.line()
    c.send("NICK judy");  c.line()
    a.send("PM ivan secret handshake")
    got = b.lines_until("PM ")
    leaked = c.lines_until("PM ", limit=2, timeout=1.0)
    a.close(); b.close(); c.close()
    return (got is not None and "secret handshake" in got and leaked is None), \
           f"target got {got!r}, third party got {leaked!r}"


def t_pm_unknown_user():
    p = Peer()
    p.send("NICK kim"); p.line()
    p.send("PM nobody_here hello")
    r = p.lines_until("ERR")
    p.close()
    return (r is not None and r.startswith("ERR 104")), f"got {r!r}"


def t_join_notice():
    a = Peer()
    a.send("NICK liam"); a.line()
    b = Peer()
    b.send("NICK mona"); b.line()
    got = a.lines_until("INFO")
    a.close(); b.close()
    return (got is not None and "mona" in got), f"got {got!r}"


# ---------------------------------------------------------------- M4 tests --
def t_abrupt_disconnect():
    """Kill a client mid-session; the survivor must keep working."""
    a, b = Peer(), Peer()
    a.send("NICK nina"); a.line()
    b.send("NICK oscar"); b.line()
    b.kill()
    time.sleep(0.4)
    a.send("MSG still here")
    r = a.lines_until("OK", timeout=2.0)
    a.close()
    return (r is not None), "server stopped responding after a peer died"


def t_nick_freed_after_disconnect():
    a = Peer()
    a.send("NICK pat"); a.line()
    a.close()
    time.sleep(0.4)
    b = Peer()
    b.send("NICK pat")
    r = b.line()
    b.close()
    return (r is not None and r.startswith("OK")), f"got {r!r} (nick never released)"


def t_large_message():
    """Payload well past one TCP segment -- exposes send() without a loop."""
    a, b = Peer(), Peer()
    a.send("NICK quinn"); a.line()
    b.send("NICK rita");  b.line()
    body = "x" * 400
    a.send("MSG " + body)
    got = b.lines_until("MSG ", timeout=4.0)
    a.close(); b.close()
    return (got is not None and got.endswith(body)), \
           f"delivered {len(got) if got else 0} chars, expected trailing {len(body)}"


def t_many_clients():
    peers = []
    try:
        for i in range(12):
            p = Peer()
            p.send(f"NICK user{i:02d}")
            if p.line() is None:
                return False, f"server stopped accepting at client {i}"
            peers.append(p)
        peers[0].send("WHO")
        r = peers[0].lines_until("USERS", limit=20)
        return (r is not None and "user11" in r), f"got {r!r}"
    finally:
        for p in peers:
            p.close()


def t_quit():
    p = Peer()
    p.send("NICK sam"); p.line()
    p.send("QUIT")
    p.lines_until("OK", timeout=2.0)
    closed = p.line(timeout=2.0)
    p.close()
    return (closed is None), "socket still open after QUIT"


def t_server_survives_garbage():
    p = Peer()
    p.send_raw(b"\x00\xff\xfe binary junk \x01\n")
    p.line(timeout=1.5)
    p.close()
    q = Peer()
    q.send("NICK afterjunk")
    r = q.line()
    q.close()
    return (r is not None and r.startswith("OK")), "server died on non-UTF8 input"


SUITE = [
    ("M2", "NICK returns OK",                       t_nick_ok),
    ("M2", "unknown verb -> ERR 100",               t_unknown_command),
    ("M2", "MSG before NICK -> ERR 103",            t_msg_before_nick),
    ("M2", "illegal nickname -> ERR 101",           t_bad_nick),
    ("M2", "one line split across 3 writes",        t_split_line),
    ("M2", "two lines in one write",                t_two_lines_one_write),
    ("M2", "partial line is not executed",          t_no_trailing_newline),
    ("M2", "oversized line handled",                t_oversized_line),
    ("M3", "broadcast reaches other client",        t_broadcast),
    ("M3", "sender does not receive own MSG",       t_no_echo_to_sender),
    ("M3", "duplicate nickname -> ERR 102",         t_duplicate_nick),
    ("M3", "WHO lists all users",                   t_who),
    ("M3", "PM reaches only the target",            t_private_message),
    ("M3", "PM to unknown user -> ERR 104",         t_pm_unknown_user),
    ("M3", "join notice broadcast",                 t_join_notice),
    ("M4", "survives an abrupt disconnect",         t_abrupt_disconnect),
    ("M4", "nickname freed on disconnect",          t_nick_freed_after_disconnect),
    ("M4", "400-byte message arrives whole",        t_large_message),
    ("M4", "12 concurrent clients",                 t_many_clients),
    ("M4", "QUIT closes the connection",            t_quit),
    ("M4", "survives non-UTF8 garbage",             t_server_survives_garbage),
]

WEIGHTS = {"M2": 25, "M3": 35, "M4": 25}


def main():
    global HOST, PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5050)
    args = ap.parse_args()
    HOST, PORT = args.host, args.port

    try:
        Peer().close()
    except OSError as e:
        print(f"Cannot reach a server at {HOST}:{PORT} -- {e}")
        print("Start the student's server first, then rerun.")
        sys.exit(2)

    print(f"\nTuskChat grader  ->  {HOST}:{PORT}\n")
    current = None
    for milestone, name, fn in SUITE:
        if milestone != current:
            current = milestone
            print(f"{milestone}")
        check(name, milestone, fn)

    print("\n" + "-" * 58)
    total = 0
    for m in ("M2", "M3", "M4"):
        got = [r for r in results if r[0] == m]
        passed = sum(1 for r in got if r[2])
        pts = WEIGHTS[m] * passed / len(got)
        total += pts
        print(f"{m}: {passed}/{len(got)} tests   {pts:5.1f} / {WEIGHTS[m]} pts")
    print(f"{'automated subtotal':<26}{total:5.1f} / 85 pts")
    print("M1 (15 pts) and the write-up are graded by hand.")
    print("-" * 58 + "\n")


if __name__ == "__main__":
    main()
