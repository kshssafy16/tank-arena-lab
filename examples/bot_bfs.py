"""Plain BFS baseline: ground/sand only; handles simple stages, no supply logic."""
from collections import deque
from bot_exam_general import DIRS, firing_direction, locate, main, parse


def decide(raw, shift=17):
    grid, stats, _ = parse(raw)
    me, target = locate(grid, 'M'), locate(grid, 'X')
    n, m = int(stats['M'][2]), int(stats['M'][3])
    if not n and not m:
        return 'S'
    queue = deque([(me, None)])
    seen = {me}
    while queue:
        pos, first = queue.popleft()
        direction = firing_direction(grid, pos, target)
        if direction:
            return first or direction+(' F M' if m and int(stats['X'][0]) > 30 else ' F' if n else ' F M')
        for direction, (dr,dc) in DIRS.items():
            nxt = pos[0]+dr, pos[1]+dc
            if 0 <= nxt[0] < len(grid) and 0 <= nxt[1] < len(grid[0]) and nxt not in seen and grid[nxt[0]][nxt[1]] in ('G','S'):
                seen.add(nxt)
                queue.append((nxt, first or direction+' A'))
    return 'S'


if __name__ == '__main__':
    main(decide)
