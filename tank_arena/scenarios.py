from __future__ import annotations

import json
from pathlib import Path
from .engine import initial_state

ROOT = Path(__file__).resolve().parent


def load_scenarios(profile: str = "public", private_root: Path | None = None) -> list[dict]:
    if profile == "public":
        folder = ROOT / "stages"
    elif profile == "private":
        folder = (private_root or ROOT.parent / ".private_reference") / "stages"
    else:
        raise ValueError("Unknown profile")
    paths = sorted(folder.glob("stage[1-6].json"))
    if profile == "public" and len(paths) != 6:
        raise ValueError("Profile must contain stage1.json through stage6.json (all six required)")
    if not paths:
        raise ValueError("No local reference stages imported; see tools/reference_import.py")
    specs = [json.loads((folder / f"stage{i}.json").read_text(encoding="utf-8"))
             if (folder / f"stage{i}.json").exists() else
             {"stage": i, "name": f"Reference {i} (not imported)", "skill": "unavailable", "available": False}
             for i in range(1, 7)]
    for i, spec in enumerate(specs, 1):
        if spec.get("stage") != i:
            raise ValueError("Scenario stage number mismatch")
        if spec.get("available", True):
            initial_state(spec, variant=False)
    return specs
