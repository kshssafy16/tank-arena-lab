"""A run owns one connection. A winning action responds with the NEXT map."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib

from .engine import initial_state, serialize, stars, step


@dataclass
class Run:
    specs: list[dict]
    mode: str = "exam"
    stage: int = 1
    seed: int = 0
    profile: str = "public"
    attempt: int = 1
    results: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    finished: bool = False
    failure: str = ""
    nickname: str = ""
    connections: int = 0
    last_variant: int = -1

    def __post_init__(self):
        if self.mode not in ("exam", "practice") or not 1 <= self.stage <= 6:
            raise ValueError("Invalid run mode/stage")
        if self.mode == "exam":
            self.stage = 1
            if any(not s.get("available", True) for s in self.specs):
                raise ValueError("Private exam requires all six imported stages")
        if not self.specs[self.stage-1].get("available", True):
            raise ValueError("This private stage has not been imported")
        self._start()

    def _start(self):
        # Two reproducible original variants; private captures stay unchanged.
        variant_seed = self.seed * 7 + (self.stage-1)*2 + self.attempt-1
        spec = self.specs[self.stage-1]
        choices = spec.get("variants")
        self.variant_index = 0
        if choices:
            digest = hashlib.sha256(f"{self.seed}:{self.stage}:{self.attempt}".encode()).digest()
            indices = [i for i in range(len(choices)) if len(choices)==1 or i != self.last_variant]
            self.variant_index = indices[int.from_bytes(digest[:4],"big") % len(indices)]
            spec = {**spec, **choices[self.variant_index]}
            self.last_variant = self.variant_index
        self.state = initial_state(spec, variant_seed, self.profile == "public")
        self.history.append({"type": "start", "stage": self.stage, "attempt": self.attempt,
                             "variant": self.variant_index, "state": self.state.snapshot(), "raw": serialize(self.state)})

    def record_failure(self, reason: str):
        if self.finished:
            return
        self.state.outcome, self.state.reason = "fail", reason
        self._finish_attempt()

    def apply(self, command: str):
        if self.finished:
            return
        before = serialize(self.state)
        self.state = step(self.state, command)
        self.history.append({"type": "turn", "stage": self.stage, "attempt": self.attempt,
                             "turn": self.state.turn, "command": command, "input": before,
                             "state": self.state.snapshot()})
        if self.state.outcome != "playing":
            self._finish_attempt()

    def _finish_attempt(self):
        me = self.state.units["M"]
        self.results.append({"stage": self.stage, "attempt": self.attempt, "turns": self.state.turn,
                             "stars": stars(self.state), "outcome": self.state.outcome,
                             "reason": self.state.reason, "hp": me.hp, "normal": me.normal,
                             "mega": me.mega, "seed": self.state.seed, "variant": self.variant_index})
        if self.state.outcome != "success":
            self.finished, self.failure = True, self.state.reason
        elif self.mode == "practice" or self.stage == 6 and self.attempt == 2:
            self.finished = True
        elif self.attempt == 1:
            self.attempt = 2
            self._start()
        else:
            self.stage += 1
            self.attempt = 1
            self._start()

    def summary(self):
        scores = []
        for stage in range(1, 7):
            attempts = [r for r in self.results if r["stage"] == stage]
            confirmed = min(r["stars"] for r in attempts) if len(attempts) == 2 else attempts[0]["stars"] if self.mode=="practice" and attempts else 0
            # A failed first attempt is a final zero; successful first is provisional.
            scores.append({"stage": stage, "attempts": deepcopy(attempts), "stars": confirmed,
                           "provisional": len(attempts) == 1 and attempts[0]["outcome"] == "success" and self.mode == "exam"})
        return {"mode": self.mode, "profile": self.profile, "seed": self.seed, "finished": self.finished,
                "failure": self.failure, "stage": self.stage, "attempt": self.attempt,
                "completed_attempts": len(self.results), "scores": scores,
                "total_stars": sum(s["stars"] for s in scores) if self.mode == "exam" else sum(r["stars"] for r in self.results),
                "connections": self.connections, "nickname": self.nickname}

    def replay(self):
        return {"format": "tank-arena-replay-v1", "summary": self.summary(),
                "scenarios": deepcopy(self.specs), "history": deepcopy(self.history), "results": deepcopy(self.results)}
