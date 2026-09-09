# Programming Assignment: TuskChat

**Topic:** TCP socket programming, application protocol design, concurrency
**Language:** Python 3.8+ (standard library only — no `asyncio`, no third-party packages)
**Work:** Individual
**Weight:** 100 points + 10 bonus
**Duration:** two weeks

---

## 1. What you are building

A **multi-client chat server** and a matching **command-line client**, speaking a
text protocol you implement to spec.

Anyone should be able to join your chat with nothing but `netcat`. That constraint
is the whole point: it forces a real protocol instead of two programs that only
happen to understand each other.

```
$ nc 127.0.0.1 5050
NICK ada
OK ada
MSG hello everyone
OK
INFO grace joined (2 online)
MSG grace hi ada
WHO
USERS 2 ada grace
QUIT
OK bye
```

You must use the `socket` module directly. Anything that hides the socket from
you — `socketserver`, `http.server`, `asyncio`, `websockets`, Flask — is not
allowed, because the graded skill is the part those libraries do for you.

---

## 2. Protocol specification — TuskChat/1.0

This section is a contract. Your server is graded against it by an automated
tester that uses raw sockets, not your client. Read it twice.

### 2.1 Framing

* Every message, in both directions, is one line terminated by a single `\n`.
* Maximum line length is **512 bytes including the newline**.
* Encoding is UTF-8. Text may contain spaces; it must not contain `\n`.
* A line is a verb, then a single space, then arguments. Verbs are matched
  case-insensitively; nicknames are case-sensitive.

**The rule that will cost you points if you ignore it:** TCP delivers a byte
stream. One `recv()` may return half a command, two commands, or one and a half.
Buffer incoming bytes and process only complete lines. Never assume one `recv()`
equals one message.

### 2.2 Client → Server

| Command | Meaning |
|---|---|
| `NICK <name>` | Register or change nickname. `[A-Za-z0-9_]`, 1–16 chars. |
| `MSG <text>` | Broadcast `<text>` to every other registered client. |
| `PM <name> <text>` | Send `<text>` privately to `<name>`. |
| `WHO` | Request the list of registered nicknames. |
| `QUIT` | Leave. Server replies, then closes the connection. |

### 2.3 Server → Client

| Reply | Meaning |
|---|---|
| `OK [detail]` | The command succeeded. |
| `ERR <code> <message>` | The command failed. |
| `MSG <nick> <text>` | A broadcast from `<nick>`. |
| `PM <nick> <text>` | A private message from `<nick>`. |
| `INFO <text>` | Server notice, e.g. `INFO grace joined (2 online)`. |
| `USERS <n> <nick> ...` | Reply to `WHO`. `<n>` is the count. |

### 2.4 Error codes

| Code | Condition |
|---|---|
| `100` | Unknown command |
| `101` | Malformed or missing arguments (includes an illegal nickname) |
| `102` | Nickname already taken |
| `103` | Command requires a nickname and none is set |
| `104` | No such user (for `PM`) |
| `105` | Line exceeds 512 bytes |

### 2.5 Required behaviours

1. A client must send `NICK` before `MSG` or `PM`. Otherwise reply `ERR 103`.
2. `MSG` goes to every registered client **except the sender**. The sender gets `OK`.
3. When a client joins, changes nickname, or leaves, every *other* client gets an `INFO` line.
4. A nickname is released the moment its connection closes, however it closes.
5. An unexpected disconnect must never take down the server or any other client.
6. A malformed line is answered with an `ERR` and the connection stays open.

---

## 3. Milestones

Work in this order. Each milestone is a working program, not a fragment.
Commit after each one — the commit history is part of what you submit.

### M1 — Echo server (15 pts)

`echo_server.py` accepts one connection at a time and sends back every line it
receives, uppercased. No protocol, no threads.

**Done when:** `nc 127.0.0.1 5050`, type `hello`, and `HELLO` comes back.
Restart your server twice in a row without seeing *Address already in use*.

### M2 — Protocol and framing (25 pts)

`server.py` handles **one** client and implements every command in §2.
Correct line buffering is the graded skill here, not the command logic.

**Done when:** these all behave correctly:
```bash
printf 'NICK ada\nWHO\n' | nc 127.0.0.1 5050        # two commands, one write
printf 'NI' ; sleep 1 ; printf 'CK ada\n'            # one command, two writes
printf 'NICK ada'                                    # no newline: nothing runs
```

### M3 — Many clients (35 pts)

Accept unlimited concurrent clients using **one thread per connection**.
Keep a shared roster of `nickname -> connection` and guard it with a
`threading.Lock`. Implement broadcast, `PM`, `WHO`, and `INFO` notices.

**Done when:** three `netcat` sessions can hold a conversation, and a fourth
client connecting does not interrupt them.

### M4 — Robustness and the client (25 pts)

`client.py` connects, reads user input, prints incoming lines as they arrive
(hint: one thread reads the socket, the main thread reads the keyboard), and
exits cleanly on `QUIT` or Ctrl-C.

Then harden the server against all of the following:

* A client killed with `kill -9` mid-session.
* A client that sends 400 bytes in a single `MSG`.
* A client that sends a 900-byte line.
* A client that connects and sends nothing at all.
* Non-UTF-8 bytes.
* Two clients claiming the same nickname at the same moment.

**Done when:** none of the above kills the server or any other client.

### Bonus (up to 10 pts) — pick one

* **Binary framing.** Add a `--binary` mode using a 4-byte big-endian length
  prefix instead of newlines, with a `recvall(n)` helper. Document it.
* **Single-threaded.** A second server, `server_select.py`, with identical
  behaviour built on `selectors` — no threads at all. Compare the two in your report.
* **File transfer.** `SEND <nick> <filename> <size>` followed by exactly `<size>`
  bytes, delivered to the target and written to disk.

---

## 4. What to submit

A single repository or zip named `lastname_tuskchat`:

```
echo_server.py     server.py     client.py
README.md          BUGLOG.md     (bonus files, if any)
```

**README.md** — how to run both programs, which milestones you completed, any
deviation from the spec and why, and anything that does not work. An honest
"M4 large-message handling is broken" earns more than a silent omission.

**BUGLOG.md** — 4 to 8 entries, one per real bug you hit. Each entry:

> **Symptom** (what you observed) → **Cause** (what was actually wrong) →
> **Fix** (what you changed) → **How you found it** (which tool or experiment)

This is graded. Bugs you had to think about are worth more than typos.

---

## 5. Demo (in lab, week 2)

Ten minutes, live, with a partner. You will be asked to:

1. Start your server and have **your partner's client** connect to it over the lab network. If it does not interoperate, your protocol does not match the spec.
2. Connect a raw `netcat` session alongside it and send a command by hand.
3. Kill one client with `kill -9` and show the others still working.
4. Explain one line of your own code that I choose.

Localhost-only testing is the most common way students fail this demo. Test
across two machines before you show up.

---

## 6. Grading

| Component | Points |
|---|---|
| M1 — echo server | 15 |
| M2 — protocol and framing | 25 |
| M3 — concurrency and broadcast | 35 |
| M4 — robustness and client | 25 |
| **Subtotal** | **100** |
| Bonus | +10 |

M2–M4 are scored by an automated tester that speaks raw sockets. It checks, among
other things: a command split across three writes, two commands in one write, a
command with no trailing newline, an over-long line, an abruptly killed client, a
400-byte broadcast, twelve simultaneous clients, and non-UTF-8 input. The tester
will be released with the assignment — **run it before you submit.**

Deductions apply for: using a forbidden library (−100% of the affected
milestone), a server that requires a restart between test runs (−5),
missing `SO_REUSEADDR` (−3), busy-waiting at 100% CPU (−5), and no `BUGLOG.md` (−10).

---

## 7. Getting unstuck

Work through this list before asking for help, and say which steps you tried:

1. Can `nc 127.0.0.1 5050` reach your server at all? If not, the bug is in the server.
2. `lsof -i :5050` — is something else already holding the port?
3. Print every chunk with `print(repr(chunk))` right after `recv()`. Almost every
   framing bug is visible in that one line of output.
4. Does an empty `recv()` result break your loop? If not, that is your 100% CPU.
5. Are you using `sendall()`? Plain `send()` may write only part of your buffer.
6. `ss -tan | grep 5050` — what state are your connections actually in?

Office hours are for bugs you have already characterised. "It does not work" is
not a bug report; step 3 turns it into one.

---

## 8. Collaboration and AI use

Discussing protocol design, debugging strategy, and error messages with
classmates is encouraged. Sharing code is not.

You may use an AI assistant, under two conditions:

1. **Disclose it.** A section in `README.md` listing what you asked for and what
   you used. Undisclosed use is an integrity violation; disclosed use is not.
2. **Own it.** In the demo you will be asked to explain a line of your code. AI-generated
   socket code fails in characteristic ways — it frequently assumes one `recv()`
   returns one message, and it often omits `SO_REUSEADDR` and the empty-`recv()`
   check. The automated tester was written specifically to catch those. If you
   cannot explain your framing logic, that milestone scores zero regardless of
   whether the tests pass.

Treat generated code the way you would treat a Stack Overflow answer from 2011:
possibly right, definitely not written for your spec.
