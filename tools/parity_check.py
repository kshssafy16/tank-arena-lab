"""Compare local observed input/command/output trace against the pure engine.

Trace JSON: {initial: raw, rules: {}, turns: [{command: 'R A', expected: raw}],
             expected_stars: 3 (optional)}. All output stays private.
Never treats the supplied Stage-1 seven-turn anecdote as a captured map.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference_import import specification
from tank_arena.engine import initial_state, serialize, stars, step
from tank_arena.protocol import parse_state


def compare(trace):
    state = initial_state(specification(trace["initial"], 1, trace.get("rules")), variant=False)
    comparisons = []
    for i, record in enumerate(trace["turns"],1):
        state = step(state, record["command"])
        actual = asdict(parse_state(serialize(state)))
        expected = asdict(parse_state(record["expected"]))
        # Code text is generated independently. Compare counts, not proprietary phrases.
        actual["codes"], expected["codes"] = len(actual["codes"]), len(expected["codes"])
        differences = [key for key in actual if actual[key] != expected[key]]
        comparisons.append({"turn": i, "command": record["command"], "matches": not differences,
                            "different_fields": differences})
    star_match = "expected_stars" not in trace or trace["expected_stars"] == stars(state)
    return {"matches": all(c["matches"] for c in comparisons) and star_match, "turns": comparisons,
            "star_match": star_match, "simulated_stars": stars(state),
            "scope": "Only supplied trace; does not establish general game parity"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace",type=Path)
    args=p.parse_args()
    result=compare(json.loads(args.trace.read_text(encoding="utf-8")))
    folder=ROOT/".private_reference";folder.mkdir(exist_ok=True)
    (folder/"parity-result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["matches"] else 1)


if __name__ == "__main__":
    main()
