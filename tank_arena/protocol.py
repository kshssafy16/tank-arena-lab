"""Count-framed state messages; no proprietary files or network dependencies."""
from __future__ import annotations

from dataclasses import dataclass
import codecs
import re
import select
import socket
import time

TILE = re.compile(r"M[1-3]?|E[1-3]|[GSWTRFHX]")


def parse_row(line: str, width: int) -> list[str]:
    cells = line.split()
    if len(cells) == 1:
        cells = TILE.findall(cells[0])
        if "".join(cells) != line.strip():
            raise ValueError("Unknown map token")
    if len(cells) != width or any(TILE.fullmatch(c) is None for c in cells):
        raise ValueError(f"Map width/token mismatch: expected {width}: {line!r}")
    return cells


@dataclass
class Packet:
    grid: list[list[str]]
    allies: dict[str, list[str]]
    enemies: dict[str, list[str]]
    codes: list[str]


def parse_state(raw: str) -> Packet:
    lines = raw.splitlines()
    try:
        h, w, a, e, c = map(int, lines[0].split())
    except (ValueError, IndexError) as exc:
        raise ValueError("Expected H W allies enemies codes") from exc
    if (h,w,a,e,c) == (0,0,0,0,0) and len(lines) == 1:
        return Packet([], {}, {}, [])
    if not (1 <= h <= 64 and 1 <= w <= 64 and 1 <= a <= 8 and 0 <= e <= 8 and 0 <= c <= 8):
        raise ValueError("Header counts out of range")
    if len(lines) != 1 + h + a + e + c:
        raise ValueError("Incomplete or multiple state messages")
    grid = [parse_row(line, w) for line in lines[1:1+h]]
    def units(rows):
        result = {}
        for line in rows:
            parts = line.split()
            if len(parts) < 2 or parts[0] in result:
                raise ValueError("Malformed or duplicate unit")
            int(parts[1])
            result[parts[0]] = parts[1:]
        return result
    allies = units(lines[1+h:1+h+a])
    enemies = units(lines[1+h+a:1+h+a+e])
    return Packet(grid, allies, enemies, lines[1+h+a+e:])


class StateStream:
    """Preserve surplus frames and fragmented UTF-8, including empty code rows."""
    def __init__(self):
        self.buffer = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")()

    def feed(self, data: bytes) -> None:
        self.buffer += self.decoder.decode(data)
        if len(self.buffer) > 262144:
            raise ValueError("State stream exceeds size limit")

    def pop(self) -> str | None:
        if "\n" not in self.buffer:
            return None
        header = self.buffer.split("\n", 1)[0]
        h, w, a, e, c = map(int, header.split())
        if (h,w,a,e,c) == (0,0,0,0,0):
            self.buffer = self.buffer.split("\n",1)[1]
            return header+"\n"
        if not (1 <= h <= 64 and 1 <= w <= 64 and 1 <= a <= 8 and 0 <= e <= 8 and 0 <= c <= 8):
            raise ValueError("Header counts out of range")
        count = 1 + h + a + e + c
        rows = self.buffer.split("\n")
        if len(rows) <= count:
            return None
        raw = "\n".join(rows[:count]) + "\n"
        parse_state(raw)
        self.buffer = "\n".join(rows[count:])
        return raw


@dataclass(frozen=True)
class Command:
    action: str
    direction: str | None = None
    option: str = ""


def parse_command(text: str) -> Command:
    p = text.strip().split()
    direction = p.pop(0) if p and p[0] in ("U", "D", "L", "R") else None
    if not p:
        raise ValueError("Missing action")
    action = p.pop(0)
    if action in ("A", "S") and not p:
        return Command(action, direction)
    if action == "F" and (not p or p == ["M"]):
        return Command(action, direction, "M" if p else "")
    if action == "G" and len(p) == 1 and re.fullmatch("[A-Z]+", p[0]):
        return Command(action, direction, p[0])
    raise ValueError("Invalid command or pipelined commands; send one command per state")


class CommandReader:
    """Newline framing or legacy trailing-space with a documented idle window.

    Legacy F<space> and F<space>M<space> are inherently ambiguous in TCP.
    Newline clients get strict framing; legacy callers get a 50 ms quiet window.
    """
    def __init__(self, conn: socket.socket, quiet: float = .05):
        self.conn, self.quiet = conn, quiet
        self.framing = None

    def read(self, timeout: float) -> str:
        end = time.monotonic() + timeout
        data = bytearray()
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("command_timeout")
            legacy_boundary = self.framing != "newline" and data and data[-1:] in (b" ", b"\t") and data.strip() != b"INIT"
            wait = min(remaining, self.quiet) if legacy_boundary else remaining
            ready, _, _ = select.select([self.conn], [], [], wait)
            if not ready:
                if legacy_boundary:
                    self.framing = "legacy"
                    return data.decode("utf-8").strip()
                continue
            block = self.conn.recv(4096)
            if not block:
                raise ConnectionError("client_disconnected")
            data.extend(block)
            if len(data) > 4096:
                raise ValueError("Command exceeds 4096 bytes")
            if b"\n" in data:
                self.framing = "newline"
                first, rest = data.split(b"\n", 1)
                if rest.strip():
                    raise ValueError("Pipelining is unsupported: stale commands rejected")
                return first.decode("utf-8").strip()
