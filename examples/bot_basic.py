"""Minimal live-state move/fire example. Intended for Stage 1 exploration."""
from bot_exam_general import firing_direction, locate, main, parse


def decide(raw, shift=17):
    grid, stats, _ = parse(raw)
    me, target = locate(grid, 'M'), locate(grid, 'X')
    direction = firing_direction(grid, me, target)
    if direction:
        return direction+' F'
    for direction, dr, dc in [('U',-1,0),('R',0,1),('D',1,0),('L',0,-1)]:
        r,c = me[0]+dr,me[1]+dc
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] in ('G','S'):
            return direction+' A'
    return 'S'


if __name__ == '__main__':
    main(decide)
