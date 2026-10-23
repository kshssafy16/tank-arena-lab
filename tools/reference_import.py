"""Import a user-owned, observed text state into the ignored local profile.

Does not extract Unity files, invoke the source program, or access a service.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tank_arena.engine import initial_state
from tank_arena.protocol import parse_state


def specification(raw, stage, rules=None, evidence="user-provided local capture"):
    packet = parse_state(raw)
    units = {}
    for symbol, values in {**packet.allies, **packet.enemies}.items():
        units[symbol] = {"hp": int(values[0])}
        if symbol == "M":
            if len(values) != 4:
                raise ValueError("Expected own HP direction normal mega")
            units[symbol].update(direction=values[1], normal=int(values[2]), mega=int(values[3]))
    spec = {"stage": stage, "name": f"Local reference {stage}", "skill": "Private observed input",
            "rows": [" ".join(row) for row in packet.grid], "units": units,
            "rules": {"parity": "private_capture_unverified", **(rules or {})},
            "provenance": {"evidence": evidence, "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                           "limitations": "Terrain under units assumed G; cipher, AI and scoring require separate evidence."}}
    initial_state(spec, variant=False)
    return spec


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="User-owned UTF-8 raw state, with final newline")
    p.add_argument("--stage", required=True, type=int, choices=range(1,7))
    p.add_argument("--rules", type=Path, help="Optional JSON Rules overrides backed by your observations")
    p.add_argument("--evidence", default="user-provided local capture")
    args = p.parse_args()
    raw = args.input.read_text(encoding="utf-8-sig")
    rules = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else None
    spec = specification(raw, args.stage, rules, args.evidence)
    dest = ROOT / ".private_reference" / "stages" / f"stage{args.stage}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(spec, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Local only: {dest}. No upload, no public map export.")


if __name__ == "__main__":
    main()
