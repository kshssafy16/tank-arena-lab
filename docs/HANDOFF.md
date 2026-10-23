# Development handoff

Updated: 2026-10-23. This backup preserves the existing engine and tests; no gameplay features were added.

## Current implementation

Python 3.11+ standard-library authoritative engine and localhost TCP/HTTP server. Stage 1–6 unlimited practice; one Python process and one TCP connection for up to 12 exam attempts. Two attempts per stage, minimum stars, immediate stop on failure. Canvas observer UI, pause/step/speed in practice, raw protocol diagnostics, results/export and deterministic replay verification. Three example bots.

Public scenarios and graphics are independently authored. Private reference inputs are optional and absent from GitHub. A fresh clone runs without the original installation.

## Validation already recorded

Previous Windows/Python 3.12.9 verification: 45 tests passed, 100 seeded full exam runs, actual subprocess/one-connection 12-attempt E2E, fresh clone/setup/run passed. Public seed0: 18 stars. Local private profile: 25 variants passed; 12 attempts/16 stars; reported Stage1 seven-turn/three-star sequence reproduced. These are historical results, not new original-game live differential tests. See TEST_REPORT.md and PARITY_REPORT.md. This preservation task runs the release/history audit; it does not change engine behavior.

## Other Windows PC

Clone the private repository using your own GitHub authentication, enter its directory, then:

```powershell
.\scripts\setup.bat
.\scripts\start.bat
# In another terminal in the same directory:
.\.venv\Scripts\python.exe examples\bot_exam_general.py
```

UI: http://127.0.0.1:8765 ; TCP: 127.0.0.1:8747. Choose Practice or Exam Simulation before starting the bot. Close the other local game if it occupies 8747. Stop server with Ctrl+C.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\release_check.py
```

Open the cloned folder in Codex. Ask it to read HANDOFF.md, NEXT_STEPS.md, RULES_MATRIX.md and PARITY_REPORT.md first, retain the existing engine/tests, and continue toward a native desktop practice simulator.

## Excluded local material

.private_reference/ contains original local map inputs/variants, targeted static analysis, manual text, analysis packages, detailed validation outputs and screenshots. runs/ contains local public replays; dist/ contains source ZIPs, verification extractions and smoke clones. .venv/, caches, binaries, original assets/manuals, logs and credentials are excluded. Original distribution and the older practice project live outside this repository and are not backed up here.

A clone cannot reproduce private-profile runs without separately restoring legally owned private inputs to .private_reference/. Do not commit those inputs even to this private repository. See LOCAL_REFERENCE.md for text-capture import. Default public mode remains usable.

## Known unfinished items

Browser UI is transitional. Native desktop game window and direct Python workflow are not implemented. Team battle is deferred. Original full live differential parity, NPC random stream, flood/unit overlap and final-turn display boundaries remain unverified. Legacy trailing-space framing has documented ambiguity; newline framing is a local extension. External bot traceback cannot be inferred from a disconnected socket.

## Publication boundary

Only private GitHub backup/push is authorized. Do not switch to public or publish a GitHub Release without explicit approval. Never upload the parent workspace or private reference files. Preserve current engine and regression tests during the future desktop UI migration.
