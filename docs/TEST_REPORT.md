# Local verification record

Date: 2026-10-23. Host: Windows, Python 3.12.9. All checks ran locally; no remote CI, push or publication.

| Check | Result | Evidence |
|---|---|---|
| `python -m unittest discover -s tests -v` | 45 PASS | 57.8s final full regression; subsequent HTTP object-validation assertion also checked in network suite |
| Seeded regression | 100/100 full runs PASS | seeds0~99, 12 attempts each, independent public scenarios; four geometric symmetries |
| Real subprocess/TCP E2E | PASS | one Python PID/connection, 12 attempts, 18 public stars, ordered results |
| Legacy space client | PASS | one connection/12 attempts; same client also tests UTF-8 nickname |
| Framing | PASS | byte-by-byte states, surplus state frames, split UTF-8 INIT, >50ms newline-command fragmentation, coalesced-command rejection |
| Failure lifecycle | PASS | first/second attempt failure, partial score preservation, timeout, disconnect, paused disconnect, reset generation, duplicate-client rejection |
| Rules and tools | PASS | collisions, water/range, 30/70 damage, separate ammo, tree removal, sand death, supply/cap, score boundaries, private import, trace mismatch, replay tampering |
| Private reference profile | 25/25 variants PASS | ignored local inventory/results; raw original maps not distributed |
| Private TCP exam | PASS | one process/connection, 12 attempts, seed0 total16 stars; deterministic replay verifies242 turns |
| Reported Stage1 observation | Matched | local static reference, seven supplied actions → seven turns/three stars; not a new original-game live observation |
| Existing local bot | PASS | unchanged file, local public Stage1 success12 turns/three stars; source hash unchanged |
| Windows setup script | PASS | venv created; no third-party package/network install needed |
| Fresh local clone | PASS | no private reference files, setup.bat → CLI server → one bot →12 attempts/18 stars |
| Browser QA | PASS | stage selection, native bot-controlled board, ammo/HP/turns, exam controls disabled, 12 attempts/18-star result, connection count1; wide and narrow responsive layouts viewed |
| JavaScript syntax | PASS | `node --check tank_arena/ui/app.js`; Node is a development check only |
| Release source scan | PASS | text-only Git files, known local reference-map matches, binary/media/credential/branding guards; private paths ignored |
| Original materials / previous project | Unchanged | only read; previous project's Git status stays clean; original bot checksum preserved |

The complete test output, local screenshots, raw compatibility evidence and private replays remain ignored. No claim is made that unit tests prove runtime parity with the original game. See [PARITY_REPORT](PARITY_REPORT.md) for the remaining differences.
