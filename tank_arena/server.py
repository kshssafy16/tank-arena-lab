"""Loopback-only TCP authority and static HTTP observer, standard library only."""
from __future__ import annotations

import argparse
import json
import select
import socket
import socketserver
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import serialize
from .exam import Run
from .protocol import CommandReader
from .scenarios import ROOT, load_scenarios


class Arena:
    def __init__(self, specs=None, output=None, timeout=None, delay=.3, profile="public", initial_mode="practice", initial_stage=1, seed=0):
        self.specs = specs or load_scenarios(profile)
        self.profile = profile
        self.output = Path(output or ROOT.parent / (".private_reference/runs" if profile == "private" else "runs"))
        self.timeout_override = timeout
        self.delay = delay
        self.lock = threading.Condition(threading.RLock())
        self.run = Run(self.specs, initial_mode, initial_stage, seed, profile)
        self.client = None
        self.paused = False
        self.permits = 0
        self.generation = 0
        self.revision = 0
        self.logs = []
        self.replay_path = ""
        self.saved = False
        self.tcp_port = 8747

    def log(self, kind, message):
        self.logs.append({"time": round(time.time(), 3), "kind": kind, "message": str(message)[:500]})
        self.logs = self.logs[-100:]
        self.revision += 1

    def configure(self, mode, stage=1, seed=0):
        with self.lock:
            candidate = Run(self.specs, mode, int(stage), int(seed), self.profile)
            if self.client:
                self.run.record_failure("user_reset")
                self.save()
                try:
                    self.client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.client = None
            self.generation += 1
            self.run = candidate
            self.paused = False
            self.permits = 0
            self.saved, self.replay_path = False, ""
            self.log("run", f"{mode}: waiting for one Python client")
            self.lock.notify_all()

    def save(self):
        if self.saved or not self.run.finished:
            return
        self.output.mkdir(parents=True, exist_ok=True)
        dest = self.output / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
        temp = dest.with_suffix(".tmp")
        temp.write_text(json.dumps(self.run.replay(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp.replace(dest)
        self.replay_path, self.saved = str(dest.resolve()), True
        self.log("result", f"Saved replay: {dest.name}")

    def view(self):
        with self.lock:
            return {"revision": self.revision, "run": self.run.summary(), "state": self.run.state.snapshot(),
                    "raw": serialize(self.run.state), "connected": self.client is not None,
                    "paused": self.paused, "delay": self.delay, "logs": list(self.logs),
                    "replay_path": self.replay_path, "tcp_port": self.tcp_port,
                    "stages": [{"stage": s["stage"], "name": s["name"], "skill": s["skill"], "available": s.get("available", True)} for s in self.specs],
                    "timeline": [{"stage": x["stage"], "attempt": x["attempt"], "turn": x["turn"],
                                  "command": x["command"], "events": x["state"]["events"]}
                                 for x in self.run.history[-80:] if x["type"] == "turn"]}

    def control(self, body):
        action = body.get("action")
        if action in ("start", "reset"):
            self.configure(body.get("mode", "practice"), body.get("stage", 1), body.get("seed", 0))
        else:
            with self.lock:
                if action in ("pause", "step", "speed", "command") and self.run.mode == "exam":
                    raise ValueError("Exam runs do not permit interactive turn controls")
                if action == "pause":
                    self.paused = not self.paused
                elif action == "step":
                    self.paused = True
                    self.permits += 1
                elif action == "speed":
                    speed = int(body["speed"])
                    if speed not in (1, 2, 5, 10):
                        raise ValueError("Speed must be 1, 2, 5, or 10")
                    self.delay = .3 / speed
                elif action == "command":
                    if self.client:
                        raise ValueError("Bot owns this run; use Pause/Step to debug")
                    if self.run.finished:
                        raise ValueError("Run is finished; Retry first")
                    self.run.apply(str(body["command"])[:4096])
                    self.save()
                else:
                    raise ValueError("Unknown action")
                self.revision += 1
                self.lock.notify_all()


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        arena = self.server.arena
        conn = self.request
        with arena.lock:
            if arena.client is not None or arena.run.finished:
                return
            arena.client = conn
            generation = arena.generation
            arena.log("connection", "TCP client connected; waiting for INIT")
        reader = CommandReader(conn)
        try:
            hello = reader.read(10)
            if not hello.startswith("INIT ") or not hello[5:].strip():
                raise ValueError("Expected INIT <nickname>")
            with arena.lock:
                if generation != arena.generation:
                    return
                arena.run.nickname = hello[5:].strip()[:12]
                arena.run.connections += 1
                arena.log("init", arena.run.nickname)
            while True:
                with arena.lock:
                    if generation != arena.generation or arena.run.finished:
                        break
                    payload = serialize(arena.run.state).encode("utf-8")
                    timeout = arena.timeout_override or arena.run.state.rules.command_timeout
                conn.sendall(payload)
                # Receive BEFORE pause: the bot is free to compute; debug waiting
                # is excluded from the next turn's command deadline.
                command = reader.read(timeout)
                with arena.lock:
                    while arena.paused and not arena.permits and generation == arena.generation:
                        arena.lock.wait(.25)
                        if generation == arena.generation:
                            ready,_,_ = select.select([conn],[],[],0)
                            if ready and not conn.recv(1,socket.MSG_PEEK):
                                raise ConnectionError("client_disconnected_while_paused")
                    if generation != arena.generation:
                        break
                    if arena.paused:
                        arena.permits -= 1
                    arena.log("command", command)
                    arena.run.apply(command)
                    arena.revision += 1
                    arena.save()
                    if arena.run.finished:
                        break
                    delay = arena.delay
                # Short, interruptible presentation delay; never held under lock.
                with arena.lock:
                    arena.lock.wait(delay)
            # Behavioral end marker; EOF follows. Outcomes stay in the local UI.
            with arena.lock:
                ended = generation == arena.generation and arena.run.finished
            if ended:
                conn.sendall(b"0 0 0 0 0\n")
        except (TimeoutError, ConnectionError, OSError, UnicodeError, ValueError) as exc:
            with arena.lock:
                if generation == arena.generation and not arena.run.finished:
                    reason = "command_timeout" if isinstance(exc, TimeoutError) else "protocol_error" if isinstance(exc, (ValueError, UnicodeError)) else "client_disconnected"
                    arena.log("error", f"{reason}: {exc}")
                    arena.run.record_failure(reason)
                    arena.save()
        except Exception as exc:
            with arena.lock:
                if generation == arena.generation:
                    arena.log("error", f"server_error: {type(exc).__name__}: {exc}")
                    arena.run.record_failure("server_error")
                    arena.save()
        finally:
            with arena.lock:
                if generation == arena.generation:
                    arena.client = None
                    arena.log("connection", "TCP closed after result" if arena.run.finished else "TCP closed")


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class HTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def respond(self, payload, mime="application/json; charset=utf-8", status=200):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.valid_host():
            return self.respond({"error": "Loopback Host required"}, status=403)
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            return self.respond(self.server.arena.view())
        if path == "/api/replay":
            with self.server.arena.lock:
                return self.respond(self.server.arena.run.replay())
        assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path not in assets:
            return self.respond({"error": "Not found"}, status=404)
        name, mime = assets[path]
        self.respond((ROOT / "ui" / name).read_bytes(), mime + "; charset=utf-8")

    def do_POST(self):
        if not self.valid_host():
            return self.respond({"error": "Loopback Host required"}, status=403)
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            return self.respond({"error": "Same-origin requests only"}, status=403)
        if self.path != "/api/control":
            return self.respond({"error": "Not found"}, status=404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Expected bounded JSON request")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            self.server.arena.control(body)
            self.respond({"ok": True})
        except (ValueError, KeyError, TypeError) as exc:
            self.respond({"error": str(exc)}, status=400)


def create_servers(arena, tcp_port=8747, http_port=8765):
    tcp = TCPServer(("127.0.0.1", tcp_port), TCPHandler)
    try:
        http = ThreadingHTTPServer(("127.0.0.1", http_port), HTTPHandler)
    except Exception:
        tcp.server_close()
        raise
    tcp.arena = http.arena = arena
    arena.tcp_port = tcp.server_address[1]
    for server in (tcp, http):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return tcp, http


def main():
    p = argparse.ArgumentParser(description="Tank Arena Lab - local Python TCP practice")
    p.add_argument("--tcp-port", type=int, default=8747)
    p.add_argument("--http-port", type=int, default=8765)
    p.add_argument("--mode", choices=["practice", "exam"], default="practice")
    p.add_argument("--stage", type=int, choices=range(1, 7), default=1)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--profile", choices=["public", "private"], default="public")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--turn-delay", type=float, default=.3, help="Presentation seconds per turn; 0 for headless verification")
    args = p.parse_args()
    try:
        if args.turn_delay < 0:
            raise ValueError("Turn delay must be nonnegative")
        arena = Arena(profile=args.profile, initial_mode=args.mode, initial_stage=args.stage, seed=args.seed, delay=args.turn_delay)
        arena.configure(args.mode, args.stage, args.seed)
        tcp, http = create_servers(arena, args.tcp_port, args.http_port)
    except (OSError, ValueError) as exc:
        p.exit(2, f"Cannot start: {exc}\nClose the other local game or select a different port/profile.\n")
    url = f"http://127.0.0.1:{http.server_port}"
    print(f"Tank Arena Lab | UI {url} | TCP 127.0.0.1:{arena.tcp_port}", flush=True)
    print("Start ONE Python bot. Ctrl+C stops the server. Results: runs/ (private profile: .private_reference/runs/)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(.25)
    except KeyboardInterrupt:
        with arena.lock:
            arena.run.record_failure("server_stopped")
            arena.save()
            arena.generation += 1
            if arena.client:
                try:
                    arena.client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            arena.lock.notify_all()
        tcp.shutdown()
        http.shutdown()
        tcp.server_close()
        http.server_close()


if __name__ == "__main__":
    main()
