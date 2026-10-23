"""Pure, deterministic turn transition. Rules are explicit practice defaults."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib

from .protocol import parse_command, parse_row

DIRECTIONS = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}


@dataclass
class Rules:
    range: int = 3
    normal_damage: int = 30
    mega_damage: int = 70
    sand_damage: int = 10
    supply_amount: int = 1
    supply_cap: int = 10
    cipher_shift: int = 17
    max_turns: int = 120
    three_stars: int = 30
    two_stars: int = 60
    command_timeout: float = 60
    invalid_command: str = "consume_turn"
    friendly_fire: bool = False
    parity: str = "practice_unverified"

    def __post_init__(self):
        if not (0 < self.three_stars <= self.two_stars <= self.max_turns <= 10000):
            raise ValueError("Require 0 < three_stars <= two_stars <= max_turns <= 10000")
        if not (1 <= self.range <= 64 and self.command_timeout > 0):
            raise ValueError("Invalid range/timeout")
        if min(self.normal_damage, self.mega_damage, self.supply_amount) <= 0 or self.sand_damage < 0:
            raise ValueError("Damage/supply settings out of range")
        if self.supply_cap < 1:
            raise ValueError("Supply cap must be positive")
        if self.invalid_command not in ("consume_turn", "fail"):
            raise ValueError("Unknown invalid command policy")


@dataclass
class Unit:
    symbol: str
    row: int
    col: int
    hp: int = 100
    direction: str = "R"
    normal: int = 0
    mega: int = 0


@dataclass
class State:
    terrain: list[list[str]]
    units: dict[str, Unit]
    rules: Rules
    seed: int = 0
    turn: int = 0
    outcome: str = "playing"
    reason: str = ""
    events: list[dict] = field(default_factory=list)
    terrain_schedule: list[dict] = field(default_factory=list)
    npc_schedule: list[dict] = field(default_factory=list)

    def grid(self):
        grid = deepcopy(self.terrain)
        for u in self.units.values():
            if u.hp > 0:
                grid[u.row][u.col] = u.symbol
        return grid

    def snapshot(self):
        return {**asdict(self), "grid": self.grid(), "stars": stars(self)}


def initial_state(spec: dict, seed: int = 0, variant: bool = True) -> State:
    rows = spec["rows"]
    if not rows or not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("Expected 1..64 map rows")
    # Spaced rows are canonical for public/private scenario files.
    width = len(rows[0].split()) if " " in rows[0].strip() else len(parse_compact(rows[0]))
    if not 1 <= width <= 64:
        raise ValueError("Map width out of range")
    grid = [parse_row(r, width) for r in rows]
    rules = Rules(**spec.get("rules", {}))
    stats = spec.get("units", {})
    units = {}
    for r, row in enumerate(grid):
        for c, symbol in enumerate(row):
            if symbol in ("M", "H", "X") or symbol.startswith(("E", "M")):
                if symbol in units:
                    raise ValueError("Duplicate unit symbol")
                values = {"hp": 100, "direction": "R", "normal": 0, "mega": 0, **stats.get(symbol, {})}
                u = Unit(symbol, r, c, **values)
                if u.hp <= 0 or u.direction not in DIRECTIONS or min(u.normal, u.mega) < 0:
                    raise ValueError("Invalid initial unit")
                units[symbol] = u
                row[c] = "G"
    if "M" not in units or "X" not in units:
        raise ValueError("Scenario requires M and X")
    # Independent practice variation only; never infer original variant rules.
    schedule = deepcopy(spec.get("terrain_schedule", []))
    for event in schedule:
        if not isinstance(event.get("turn"),int) or event["turn"] < 1:
            raise ValueError("Terrain schedule requires a positive turn")
        for cell in event["changes"]:
            if not (0 <= cell["row"] < len(grid) and 0 <= cell["col"] < width and cell["tile"] in ("G","S","W","T","R","F")):
                raise ValueError("Invalid terrain schedule cell")
    if variant and seed % 2:
        grid = [list(reversed(row)) for row in grid]
        for u in units.values():
            u.col = width - 1 - u.col
            u.direction = {"L": "R", "R": "L"}.get(u.direction, u.direction)
        for event in schedule:
            for cell in event["changes"]:
                cell["col"] = width - 1 - cell["col"]
    if variant and (seed // 2) % 2:
        grid.reverse()
        for u in units.values():
            u.row = len(grid) - 1 - u.row
            u.direction = {"U": "D", "D": "U"}.get(u.direction, u.direction)
        for event in schedule:
            for cell in event["changes"]:
                cell["row"] = len(grid)-1-cell["row"]
    npc_schedule = deepcopy(spec.get("npc_schedule", []))
    for event in npc_schedule:
        if event.get("unit") not in units or event.get("turn",0) < 1 or any(c not in DIRECTIONS for c in event.get("directions",[])):
            raise ValueError("Invalid NPC schedule")
    return State(grid, units, rules, seed, terrain_schedule=schedule, npc_schedule=npc_schedule)


def parse_compact(line):
    from .protocol import TILE
    cells = TILE.findall(line.strip())
    if "".join(cells) != line.strip():
        raise ValueError("Unknown map token")
    return cells


def caesar(text: str, shift: int) -> str:
    return "".join(chr((ord(ch)-65+shift) % 26 + 65) if "A" <= ch <= "Z" else ch for ch in text)


def supplies(state: State) -> list[tuple[tuple[int, int], str, str]]:
    u = state.units["M"]
    choices = ("VECTOR", "ORBIT", "CIRCUIT", "SIGNAL", "TARGET", "ROCKET", "ARMOR")
    result = []
    for dr, dc in DIRECTIONS.values():
        r, c = u.row+dr, u.col+dc
        if 0 <= r < len(state.terrain) and 0 <= c < len(state.terrain[0]) and state.terrain[r][c] == "F":
            # Stable across Python versions/processes, unlike built-in hash().
            index = int.from_bytes(hashlib.sha256(f"{state.seed}:{state.turn}:{r}:{c}".encode()).digest()[:4], "big")
            plain = choices[index % len(choices)]
            result.append(((r, c), plain, caesar(plain, state.rules.cipher_shift)))
    return result


def serialize(state: State) -> str:
    allies = [u for u in state.units.values() if u.hp > 0 and u.symbol.startswith("M") or u.hp > 0 and u.symbol == "H"]
    enemies = [u for u in state.units.values() if u.hp > 0 and (u.symbol.startswith("E") or u.symbol == "X")]
    allies.sort(key=lambda u: (0 if u.symbol == "M" else 2 if u.symbol == "H" else 1, u.symbol))
    enemies.sort(key=lambda u: (u.symbol == "X", u.symbol))
    codes = [code for _, _, code in supplies(state)]
    rows = [f"{len(state.terrain)} {len(state.terrain[0])} {len(allies)} {len(enemies)} {len(codes)}"]
    rows += [" ".join(row) for row in state.grid()]
    rows += [f"{u.symbol} {u.hp} {u.direction} {u.normal} {u.mega}" if u.symbol == "M" else f"{u.symbol} {u.hp}" for u in allies]
    rows += [f"{u.symbol} {u.hp}" for u in enemies]
    return "\n".join(rows + codes) + "\n"


def stars(state: State) -> int:
    if state.outcome != "success":
        return 0
    return 3 if state.turn <= state.rules.three_stars else 2 if state.turn <= state.rules.two_stars else 1


def step(state: State, text: str) -> State:
    s = deepcopy(state)
    s.events = []
    if s.outcome != "playing":
        return s
    s.turn += 1
    me = s.units["M"]
    def emit(kind, **values):
        s.events.append({"kind": kind, **values})
    try:
        cmd = parse_command(text)
    except ValueError as exc:
        emit("invalid_command", message=str(exc))
        if s.rules.invalid_command == "fail":
            s.outcome, s.reason = "fail", "invalid_command"
        cmd = None
    if cmd:
        if cmd.direction:
            me.direction = cmd.direction
        dr, dc = DIRECTIONS[me.direction]
        if cmd.action == "A":
            r, c = me.row+dr, me.col+dc
            occupied = any(u.hp > 0 and (u.row, u.col) == (r, c) for u in s.units.values())
            if 0 <= r < len(s.terrain) and 0 <= c < len(s.terrain[0]) and s.terrain[r][c] in ("G", "S") and not occupied:
                origin = [me.row, me.col]
                me.row, me.col = r, c
                emit("move", origin=origin, target=[r, c])
                if s.terrain[r][c] == "S":
                    me.hp = max(0, me.hp - s.rules.sand_damage)
                    emit("sand", damage=s.rules.sand_damage)
            else:
                emit("blocked_move", target=[r, c])
        elif cmd.action == "F":
            ammo = "mega" if cmd.option == "M" else "normal"
            if getattr(me, ammo) <= 0:
                emit("empty_ammo", ammo=ammo)
            else:
                setattr(me, ammo, getattr(me, ammo)-1)
                damage = s.rules.mega_damage if ammo == "mega" else s.rules.normal_damage
                path = []
                for distance in range(1, s.rules.range+1):
                    r, c = me.row+dr*distance, me.col+dc*distance
                    if not (0 <= r < len(s.terrain) and 0 <= c < len(s.terrain[0])):
                        break
                    path.append([r, c])
                    target = next((u for u in s.units.values() if u.hp > 0 and (u.row, u.col) == (r, c)), None)
                    if target:
                        friendly = target.symbol.startswith("M") or target.symbol == "H"
                        if friendly and target.symbol != "H" and not s.rules.friendly_fire:
                            continue
                        if not friendly or s.rules.friendly_fire or target.symbol == "H":
                            target.hp = max(0, target.hp-damage)
                            emit("hit", target=target.symbol, damage=damage, hp=target.hp)
                            if target.hp == 0:
                                emit("destroy", target=target.symbol, position=[r, c])
                        break
                    if s.terrain[r][c] == "T":
                        s.terrain[r][c] = "G"
                        emit("tree_destroy", position=[r, c])
                        break
                    if s.terrain[r][c] in ("R", "F"):
                        emit("blocked_shot", position=[r, c])
                        break
                emit("shot", origin=[me.row, me.col], path=path, ammo=ammo)
        elif cmd.action == "G":
            # Codes belong to the state delivered BEFORE this command consumed a turn.
            if any(plain == cmd.option for _, plain, _ in supplies(state)) and me.mega < s.rules.supply_cap:
                amount = min(s.rules.supply_amount, s.rules.supply_cap-me.mega)
                me.mega += amount
                emit("supply", amount=amount)
            else:
                emit("supply_failed")
        else:
            emit("wait")
    for event in s.terrain_schedule:
        if event["turn"] == s.turn:
            for cell in event["changes"]:
                s.terrain[cell["row"]][cell["col"]] = cell["tile"]
                emit("terrain_change", position=[cell["row"],cell["col"]], tile=cell["tile"])
    # Optional local scenario scripts. Static public enemies remain static unless
    # a scenario explicitly schedules a move; no speculative global enemy AI.
    if s.units["X"].hp > 0 and me.hp > 0:
        for event in s.npc_schedule:
            if event["turn"] != s.turn:
                continue
            npc = s.units[event["unit"]]
            if npc.hp <= 0:
                continue
            options = event.get("directions", list(DIRECTIONS))
            index = int.from_bytes(hashlib.sha256(f"npc:{s.seed}:{s.turn}:{npc.symbol}".encode()).digest()[:4],"big")
            npc.direction = options[index % len(options)]
            dr,dc = DIRECTIONS[npc.direction]
            r,c = npc.row+dr,npc.col+dc
            if 0 <= r < len(s.terrain) and 0 <= c < len(s.terrain[0]) and s.terrain[r][c] in ("G","S") and not any(u.hp>0 and (u.row,u.col)==(r,c) for u in s.units.values()):
                npc.row,npc.col=r,c
                emit("npc_move", unit=npc.symbol, target=[r,c])
    if s.outcome == "playing":
        if me.hp <= 0:
            s.outcome, s.reason = "fail", "player_destroyed"
        elif "H" in s.units and s.units["H"].hp <= 0:
            s.outcome, s.reason = "fail", "friendly_turret_destroyed"
        elif s.units["X"].hp <= 0:
            s.outcome, s.reason = "success", "target_destroyed"
        elif s.turn >= s.rules.max_turns:
            s.outcome, s.reason = "fail", "turn_limit"
    return s
