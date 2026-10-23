"""Standalone resource-aware baseline. No map/stage ID is hardcoded.

Run this ONE file once for the entire exam. No optimality guarantee.
Only Python's standard library is used; safe to copy to another directory.
"""
from __future__ import annotations

import argparse
import codecs
import heapq
import itertools
import os
import re
import socket

DIRS = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
TOKENS = re.compile(r"M[1-3]?|E[1-3]|[GSWTRFHX]")


def parse(raw):
    lines = raw.splitlines()
    h, w, a, e, c = map(int, lines[0].split())
    if len(lines) != 1+h+a+e+c:
        raise ValueError("Incomplete game state")
    grid = []
    for line in lines[1:1+h]:
        cells = line.split()
        if len(cells) == 1:
            cells = TOKENS.findall(cells[0])
            if ''.join(cells) != line.strip():
                raise ValueError("Invalid map token")
        if len(cells) != w:
            raise ValueError("Map width mismatch")
        grid.append(cells)
    stats = {}
    for line in lines[1+h:1+h+a+e]:
        k, *v = line.split()
        stats[k] = v
    return grid, stats, lines[1+h+a+e:]


def locate(grid, symbol):
    return next(((r,c) for r,row in enumerate(grid) for c,t in enumerate(row) if t == symbol), None)


def firing_direction(grid, pos, target):
    for direction, (dr, dc) in DIRS.items():
        for dist in range(1, 4):
            r, c = pos[0]+dr*dist, pos[1]+dc*dist
            if not (0 <= r < len(grid) and 0 <= c < len(grid[0])):
                break
            if (r, c) == target:
                return direction
            if grid[r][c] not in ("G", "S", "W", "M", "M1", "M2", "M3"):
                break
    return None


def ammunition_options(normal, mega, hp):
    """Non-dominated combinations; keeps scarce mega rounds available for X."""
    result = []
    for m in range(min(mega, (hp+69)//70)+1):
        n = max(0, (hp-70*m+29)//30)
        if n <= normal:
            result.append((n+m, n, m))
    return sorted(result)


def plan(grid, stats, goal, hp, normal, mega, target_hp=0):
    """Dijkstra over position, HP and ammunition; returns only the first action.

    Trees/enemies are charged before entry, replanning after every real action.
    It is a baseline and may revisit cleared paths on adversarial custom maps.
    """
    start = locate(grid, "M")
    serial = itertools.count()
    queue = [(0, next(serial), start, hp, normal, mega, None)]
    seen = {}
    while queue:
        cost, _, pos, health, n, m, first = heapq.heappop(queue)
        key = (pos, health, n, m)
        if cost > seen.get(key, float("inf")):
            continue
        direction = firing_direction(grid, pos, goal) if target_hp else None
        if target_hp and direction:
            options = ammunition_options(n, m, target_hp)
            if options:
                _, nn, mm = options[0]
                shot = direction + (" F M" if mm else " F")
                return first or shot
        if not target_hp and abs(pos[0]-goal[0])+abs(pos[1]-goal[1]) == 1:
            return first or "S"
        for direction, (dr, dc) in DIRS.items():
            r, c = pos[0]+dr, pos[1]+dc
            if not (0 <= r < len(grid) and 0 <= c < len(grid[0])):
                continue
            tile = grid[r][c]
            damage = 10 if tile == "S" else 0
            if health <= damage:
                continue
            choices = [(0, 0, 0)]
            if tile == "T":
                # One shot removes a tree, regardless of round type.
                choices = [(1, 1, 0)] if n else [(1, 0, 1)] if m else []
            elif tile.startswith("E"):
                choices = ammunition_options(n, m, int(stats[tile][0]))
            elif tile not in ("G", "S", "M"):
                continue
            for shots, nn, mm in choices:
                nxt = ((r,c), health-damage, n-nn, m-mm)
                # Prefer safe ground and conserve ammunition on near ties.
                newcost = cost + 1 + shots + damage*.06 + (nn+mm)*.01
                if newcost >= seen.get(nxt, float("inf")):
                    continue
                seen[nxt] = newcost
                action = direction + (" F M" if mm else " F") if shots else direction+" A"
                heapq.heappush(queue, (newcost, next(serial), (r,c), health-damage, n-nn, m-mm, first or action))
    return None


def decide(raw, shift=17):
    grid, stats, codes = parse(raw)
    me, target = locate(grid, "M"), locate(grid, "X")
    if me is None or target is None:
        return "S"
    hp, _, n, m = stats["M"]
    hp, n, m = int(hp), int(n), int(m)
    target_hp = int(stats["X"][0])
    move = plan(grid, stats, target, hp, n, m, target_hp)
    if move:
        return move
    if codes:
        plain = ''.join(chr((ord(ch)-65-shift) % 26+65) if 'A' <= ch <= 'Z' else ch for ch in codes[0])
        return 'G '+plain
    candidates = []
    for r, row in enumerate(grid):
        for c, tile in enumerate(row):
            if tile == "F":
                action = plan(grid, stats, (r,c), hp, n, m)
                if action:
                    candidates.append((abs(r-me[0])+abs(c-me[1]), action))
    return min(candidates)[1] if candidates else "S"


class Reader:
    def __init__(self):
        self.buffer = ""
        self.decoder = codecs.getincrementaldecoder('utf-8')()

    def read(self, sock):
        while True:
            if '\n' in self.buffer:
                header = self.buffer.split('\n',1)[0]
                h,w,a,e,c = map(int, header.split())
                if (h,w,a,e,c) == (0,0,0,0,0):
                    self.buffer = self.buffer.split('\n',1)[1]
                    return None
                if not (0 < h <= 64 and 0 < w <= 64 and 0 <= a <= 8 and 0 <= e <= 8 and 0 <= c <= 8):
                    raise ValueError('Invalid state counts')
                count = 1+h+a+e+c
                lines = self.buffer.split('\n')
                if len(lines) > count:
                    raw = '\n'.join(lines[:count])+'\n'
                    self.buffer = '\n'.join(lines[count:])
                    return raw
            data = sock.recv(8192)
            if not data:
                if self.buffer:
                    raise ValueError('Truncated state at EOF')
                return None
            self.buffer += self.decoder.decode(data)
            if len(self.buffer) > 262144:
                raise ValueError('State exceeds size limit')


def main(decider=decide):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8747)
    p.add_argument('--nickname', default='ArenaBot')
    p.add_argument('--shift', type=int, default=17, help='Practice cipher shift; verify private profiles separately')
    p.add_argument('--legacy', action='store_true', help='Send trailing-space commands instead of newline')
    args = p.parse_args()
    commands = 0
    with socket.create_connection(('127.0.0.1',args.port),timeout=70) as sock:
        ending = ' ' if args.legacy else '\n'
        sock.sendall(('INIT '+args.nickname+ending).encode())
        print(f'PID={os.getpid()} CONNECTIONS=1', flush=True)
        reader = Reader()
        while True:
            raw = reader.read(sock)
            if raw is None:
                print(f'EOF: server ended run; inspect UI result. COMMANDS={commands}', flush=True)
                return
            command = decider(raw, args.shift)
            print(command, flush=True)
            sock.sendall((command+ending).encode())
            commands += 1


if __name__ == '__main__':
    main()
