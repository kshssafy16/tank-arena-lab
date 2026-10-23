# Tank Arena Lab

Python 알고리즘으로 탱크를 조종하는 **로컬 설치형 연습 시뮬레이터**입니다. Python 3.11 이상과 브라우저만 있으면 됩니다. 런타임·테스트 의존성이 없으며 설치 후 오프라인으로 실행됩니다. 웹 배포나 계정이 필요하지 않습니다.

**핵심 기능:** Stage 1~6 개별 무제한 연습, **한 Python 프로세스·한 TCP 연결로 6단계 × 2회**, 실패 즉시 종료, 두 시도 중 최저 별점, 결과·리플레이 자동 저장, 원문/명령/이벤트 디버깅.

공개판의 맵·그래픽·점수표는 독립 제작했습니다. 개인 참조 자료를 가져오는 별도 프로필을 지원합니다. **공식 평가와 100% 동일한 제품은 아닙니다.** 원본 실행 화면과의 전체 차등 검증은 미완료입니다. 확인 범위와 차이는 [PARITY_REPORT](docs/PARITY_REPORT.md)에 있습니다.

## Windows: clone → 실행 → 봇 → 결과

공개 저장소가 만들어진 뒤 GitHub의 **Code → 복사한 clone URL**로 clone하고, 프로젝트 폴더에 들어옵니다. 현재 배포용 원격 저장소는 아직 생성하지 않았습니다.

```powershell
git clone <복사한-clone-URL> tank-arena
cd tank-arena
.\scripts\setup.bat
.\scripts\start.bat
```

또는 Python 설치 후 `START_WINDOWS.bat`를 더블클릭합니다. Python Launcher(`py`)가 없으면 아래 직접 실행 경로를 사용하세요.

브라우저가 **http://127.0.0.1:8765**에서 열립니다. 왼쪽 **Stage Practice** 또는 **Exam Simulation**을 선택하고, **다른 터미널**을 같은 프로젝트 폴더에서 열어 한 번 실행합니다.

```powershell
.\.venv\Scripts\python.exe examples\bot_exam_general.py
```

시험 중에는 봇을 다시 실행하거나 연결하지 않습니다. 종료 시 UI의 `Run Results`에서 단계별 1차/2차 별점과 턴 수, 최저 별점, 합계, 실패 이유를 확인합니다. `Export`로 JSON을 저장할 수 있고 `runs/`에도 자동 저장됩니다. 서버 종료는 서버 터미널에서 **Ctrl+C**입니다.

## 가장 짧은 직접 실행

가상환경 없이도 외부 패키지 설치가 필요 없습니다.

```powershell
python run.py --mode exam
# 다른 터미널에서 한 번만 실행
python examples/bot_exam_general.py
```

서버 기본은 Stage 1 연습입니다. 바로 Stage 6 연습: `python run.py --stage 6 --seed 3`.

원본 로컬 게임이 TCP **8747**을 사용 중이면 먼저 종료하세요. 충돌 시 양쪽 포트를 함께 바꿉니다.

```powershell
python run.py --tcp-port 8877 --http-port 8878 --no-browser
python examples/bot_exam_general.py --port 8877
```

UI 접속 주소는 위 설정에서 `http://127.0.0.1:8878`입니다. 127.0.0.1에만 바인딩합니다.

## 내 Python 코드 사용

신뢰하는 자신의 스크립트를 PC에서 직접 실행합니다. UI는 Python 코드를 업로드하거나 실행하지 않습니다. 기존 소켓 코드가 `127.0.0.1:8747`, `INIT nickname`, 상태 수신 → 명령 송신을 사용한다면 우선 그대로 연결해 보세요.

- `examples/bot_basic.py`: 최소 이동/사격 예제. 범용 완주용이 아닙니다.
- `examples/bot_bfs.py`: 일반 지형/모래의 BFS. 나무·보급 문제는 해결하지 못합니다.
- `examples/bot_exam_general.py`: 단일 파일 범용 기본 봇. 자원·체력·나무·보급을 고려해 매 턴 재계획합니다. 정답·최적 턴을 보장하지 않습니다.

새 예제는 줄바꿈으로 명령을 구분합니다. 기존의 끝 공백 방식도 받지만 TCP 특성상 `F `와 `F M `의 경계를 항상 보장할 수는 없습니다. 자세한 제약과 종료 신호는 [PROTOCOL](docs/PROTOCOL.md)을 확인하세요.

## Bot Lab / 결과 / 리플레이

연습에서 Pause, 1 Turn, ×1/×2/×5/×10을 사용할 수 있습니다. Pause는 봇이 보낸 다음 명령을 엔진 적용 직전에 멈춥니다. 모의평가에서는 수동 명령과 턴 제어를 차단합니다. Retry/Reset은 기존 연결을 종료하고 초기화하므로 봇을 새로 실행해야 합니다.

아래쪽 Bot Lab에 수신 원문, 상태·이벤트, 명령 기록, 소켓 진단이 표시됩니다. 봇이 연결되지 않은 연습에서는 `R A`, `R F` 같은 명령을 직접 입력할 수도 있습니다. 로컬 JSON 리플레이 파일을 열고 슬라이더로 각 상태를 확인하세요. `Live로 돌아가기`로 현재 게임에 복귀합니다.

```powershell
python tools/verify_replay.py runs/<결과파일>.json
```

리플레이에는 seed, 전체 시나리오와 초기 상태, 명령 및 전이 상태, 시도별 체력/탄약/턴/별점, 실패 원인이 들어갑니다. 서버는 봇 프로세스를 소유하지 않으므로 연결 종료만으로 런타임 예외와 사용자의 수동 종료를 구별할 수 없습니다. **Python traceback은 봇 터미널**에서 확인합니다. 종료 신호 뒤 연결 해제는 결과를 실패로 덮어쓰지 않습니다.

## 개인 전용 참조 프로필

합법적으로 소유한 로컬 자료를 직접 관찰한 UTF-8 입력 캡처로 가져올 수 있습니다. 원본 프로그램을 실행하거나 인증에 접속하는 기능은 없습니다.

```powershell
python tools/reference_import.py --input <내-캡처.txt> --stage 1 --rules <내-규칙.json>
python run.py --profile private --stage 1
```

`--rules`는 생략할 수 있습니다. 생략된 값은 **연습 기본값**입니다. 규칙 근거 없이 공식 값으로 간주하지 마세요. 한 단계만 가져왔으면 그 단계의 연습이 가능하고, 개인 프로필의 시험에는 6개 단계가 모두 필요합니다.

```powershell
python run.py --profile private --mode exam
python examples/bot_exam_general.py
python tools/parity_check.py <내-관찰-trace.json>
```

맵과 결과는 `.private_reference/`에만 저장되고 Git/배포에서 제외됩니다. 이 개발 PC에는 별도 정적 분석으로 만든 비공개 참조 프로필이 있으며, **clone된 공개판에는 들어가지 않습니다**. 공개판과 참조 프로필은 같은 엔진을 사용합니다. 캡처 import와 비교 형식은 [로컬 검증 안내](docs/LOCAL_REFERENCE.md)에 있습니다.

## 테스트 / 배포 소스 만들기

```powershell
.\scripts\test.bat
# 또는
python -m unittest discover -s tests -v
python tools/release_check.py
# 검토된 소스가 Git에 추가된 뒤
python tools/build_release.py
```

테스트는 100개 seed에서 전체 시험, 별점 경계, 실패 중단, 분할/합쳐진 스트림, 실제 하위 Python 프로세스의 동일 연결 12회, HTTP와 로컬 참조/유출 방지를 검증합니다. 공개 변형은 **4개의 대칭 배치**와 seed 기반 보급/NPC 선택이며 100개의 독립 맵 생성이라는 뜻은 아닙니다.

ZIP은 Git 추적 소스만으로 `dist/`에 생성됩니다. 원본 바이너리·매뉴얼·맵·브랜드·로그·인증값·분석 도구를 포함하지 않습니다. 검사기는 알려진 파일 형식/문구/비공개 맵 일치를 차단하지만 모든 권리 문제를 자동 판정하지는 않습니다. CI는 테스트/빌드만 하며 게시하지 않습니다. 원격 push·공개 릴리스 기능은 없습니다.

## macOS / Linux

```sh
sh scripts/setup.sh
sh scripts/start.sh
# 다른 터미널
.venv/bin/python examples/bot_exam_general.py
```

직접 `python3 run.py`도 가능합니다. 실제 검증은 Windows/Python 3.12에서 수행했으며 macOS/Linux 실기 검증은 아직 하지 않았습니다. CI 구성은 포함되어 있으나 원격 실행 전입니다.

## 구성과 범위

`tank_arena/engine.py` 순수 상태 전이 → `exam.py` 시험 진행 → `server.py` TCP/HTTP 단일 권위 → `ui/` 관찰 화면으로 분리했습니다. [규칙 근거](docs/RULES_MATRIX.md), [시험 흐름](docs/EXAM_FLOW.md), [분석 기록](docs/RESEARCH.md), [문제 해결](docs/TROUBLESHOOTING.md)을 참고하세요.

Team Arena, 맵 편집기, 내장 코드 편집기는 아직 구현하지 않았습니다. 평가 연습을 우선합니다. 직접 작성한 소스·맵·Canvas 그래픽은 MIT 라이선스이며 개인 참조 자료와 사용자 코드에는 적용되지 않습니다.
