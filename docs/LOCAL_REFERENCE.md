# Local-only validation

공개판은 원본 설치 없이 동작한다. 개인 자료의 위치는 프로젝트의 `.private_reference/`로 고정하고 Git 추적 및 배포에서 제외한다. 참조 프로필의 결과 역시 그 아래 `runs/`로 저장한다.

## 관찰한 상태 가져오기

`reference_import.py`는 사용자가 가진 UTF-8 텍스트 상태를 파싱해 지도/자신의 체력·방향·탄약/다른 유닛 HP를 보존한다. `--rules`의 JSON으로 `Rules`의 필드를 덮어쓸 수 있다. 유닛 밑에 가려진 지형은 알 수 없어 G로 가정하므로, 캡처 한 장만으로 모든 초기 조건을 확정하지 않는다.

6개의 독립 `stage1.json`~`stage6.json`을 모두 가져와야 개인 시험을 실행할 수 있다. 한 단계만 가져왔으면 `--profile private --stage N`으로 해당 연습을 실행한다. 가져온 자료가 없는 단계는 UI에서 비활성화한다. 개인 지도는 임의 반전하지 않는다.

시나리오 JSON은 `rows`(공백 토큰의 문자열 배열), `units`(symbol별 HP/direction/normal/mega), `rules`를 갖는다. 선택적 `variants`는 같은 구조의 덮어쓰기 배열이다. `terrain_schedule`은 `[{"turn":2,"changes":[{"row":0,"col":1,"tile":"W"}]}]`처럼 관찰한 턴별 변경을 담는다. `npc_schedule`은 turn/unit/directions를 명시한다. 범용 스크립트 기능이며 특정 비공개 좌표나 맵은 공개 소스에 없다.

## 명령-상태 차등 비교

```
{
  "initial": "...실제 관찰한 첫 상태...\n",
  "rules": {"sand_damage": 0},
  "turns": [
    {"command": "R A", "expected": "...동일 명령 후 실제 관찰 상태...\n"}
  ],
  "expected_stars": 3
}
```

`python tools/parity_check.py <trace.json>`은 해당 관찰 trace를 엔진으로 재생하고 grid/allies/enemies/암호 개수를 비교한다. 암호 문장 자체는 독립 생성하므로 문자열 일치를 요구하지 않는다. 결과는 `.private_reference/parity-result.json`이다. 전체 규칙의 동일성을 입증하는 도구로 과장하지 않는다. 실패한 비교는 종료 코드1이다.

`python tools/check_local_bot.py <내봇.py> --profile private --mode exam`은 봇 소스 파일을 바꾸지 않고 자신의 PC에서 실행해 소스 해시 불변과 결과를 비공개로 저장한다. 기본 포트 8747이며 이 포트에 기존 게임이 실행 중이면 시작에 실패한다. 신뢰하는 자신의 파일에만 사용한다. 결과는 게임 서버의 상태에 근거하며 Python 예외와 수동 종료를 소켓만으로 식별할 수 없다는 한계가 있다.

이 개발 PC의 추가 정적 분석 도구/지도/상세 보고는 비공개 폴더에 있다. 이 도구를 제품에 포함하지 않으며 공개 clone은 그 파일에 접근하지 않는다. 로그인/인증/제출/자동 응시 기능은 구현하지 않았다. 원본을 변경하거나 패치하지 않는다.
