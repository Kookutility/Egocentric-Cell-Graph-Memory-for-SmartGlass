# 스마트 글래스 실내 백트래킹 프로토타입 설치/실행 가이드

이 문서는 **처음 하는 사람 기준으로**, 이 저장소를 내려받은 뒤부터 **Python 서버 실행**, **Unity 프로젝트 구성**, **실시간 연동 확인**, **백트래킹 테스트**, **결과 파일 확인**까지 전 과정을 한국어로 설명합니다.

---

## 1. 이 프로젝트가 하는 일

이 프로젝트는 실내에서 스마트 글래스가 지나온 길을 기억했다가, 나중에 **정성적(qualitative) 셀 그래프**를 이용해서 되돌아가는 안내를 주는 프로토타입입니다.

핵심은 다음과 같습니다.

- Unity가 실내 시뮬레이터 역할을 합니다.
  - RGB 카메라 화면 생성
  - 플레이어 이동
  - yaw(방향각) 생성
  - Python으로 프레임 + yaw 전송
- Python이 인식/추론 역할을 합니다.
  - 장면 분류
  - 문/사람 등 감지
  - 복도 축 감지
  - 셀 그래프 생성
  - 백트래킹 안내 생성
- 결과를 다시 Unity로 보내서 화면에 표시합니다.

중요 제약:

- **SLAM을 쓰지 않습니다.**
- **정밀 거리 기반 metric map을 만들지 않습니다.**
- **cell graph 기반 route memory만 사용합니다.**

---

## 2. 전체 실행 순서 한눈에 보기

처음 실행할 때는 아래 순서로 진행하면 됩니다.

1. Git 저장소 받기
2. Python 3.11 설치
3. Unity Hub + Unity Editor 설치
4. Python 가상환경 만들기
5. Python 패키지 설치
6. Python 서버 실행
7. Unity 프로젝트 열기
8. `DemoIndoorScene` 구성
9. Unity에서 Play 실행
10. Unity UI에서 Start Session 클릭
11. WASD / 마우스로 이동
12. Backtrack 버튼 클릭
13. Python 출력 파일 확인

---

## 3. 사전 준비물

### 3.1 필수 설치 항목

아래는 최소 필요 항목입니다.

#### 공통
- Git
- Python 3.11
- pip
- Unity Hub
- Unity 6.x Editor

#### Python 쪽
- 가상환경 도구(`venv`)
- C/C++ 런타임(일부 패키지 설치 시 필요)

#### Unity 쪽
- TextMeshPro 패키지(대부분 기본 포함)
- CharacterController 사용 가능한 3D 프로젝트

---

## 4. 운영체제별 권장 환경

### 4.1 Windows 권장
- Windows 10/11
- Python 3.11 x64
- Unity Hub 최신 버전
- Unity 6.x
- Visual Studio 또는 Rider (C# 편집용)

### 4.2 macOS 권장
- macOS 최신 버전
- Python 3.11
- Unity Hub + Unity 6.x
- VS Code / Rider / Visual Studio for Mac 대체 편집기

### 4.3 Linux 권장
- Ubuntu 22.04+ 권장
- Python 3.11
- Unity Hub + Unity 6.x

---

## 5. 저장소 받기

터미널에서 아래처럼 실행합니다.

```bash
git clone <이-저장소-URL>
cd Egocentric-Cell-Graph-Memory-for-SmartGlass
```

저장소 루트에는 대략 아래가 있습니다.

- `Assets/` : Unity 관련 스크립트/씬 가이드
- `python_server/` : FastAPI 서버 및 추론 로직
- `docs/SETUP_KO.md` : 지금 보고 있는 한국어 가이드
- `README.md` : 영문 요약 문서

---

## 6. Python 3.11 설치

### 6.1 Windows

1. Python 공식 사이트에서 Python 3.11 설치 파일을 받습니다.
2. 설치할 때 **Add Python to PATH** 체크합니다.
3. 설치 후 터미널에서 확인합니다.

```bash
python --version
pip --version
```

### 6.2 macOS / Linux

가능하면 `python3.11` 명령이 있는지 먼저 확인합니다.

```bash
python3.11 --version
```

없다면 패키지 매니저로 설치합니다.

예시:

```bash
# Ubuntu 예시
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

---

## 7. Python 가상환경 만들기

저장소 루트에서 아래를 실행합니다.

### Windows PowerShell

```powershell
cd python_server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
cd python_server
python3.11 -m venv .venv
source .venv/bin/activate
```

가상환경이 켜지면 프롬프트 앞에 `(.venv)` 같은 표시가 붙습니다.

---

## 8. Python 패키지 설치

가상환경이 켜진 상태에서 아래를 실행합니다.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

설치되는 대표 패키지:

- `fastapi`
- `uvicorn`
- `opencv-python`
- `numpy`
- `scipy`
- `ultralytics`
- `torch`
- `torchvision`
- `transformers`
- `pydantic`

> 참고: GPU 환경이 없거나 PyTorch 설치가 어려우면 시간이 오래 걸릴 수 있습니다.
> 현재 이 저장소의 기본 구현은 **모델이 없어도 heuristic fallback**으로 최소 데모가 가능하도록 되어 있습니다.

---

## 9. Python 서버 구조 이해하기

Python 서버 핵심 파일은 아래입니다.

- `python_server/app/server.py`
  - FastAPI 앱
  - HTTP 엔드포인트
  - WebSocket 엔드포인트
- `python_server/app/logic/runtime_engine.py`
  - 프레임 1장 들어올 때마다 전체 처리
- `python_server/app/logic/event_parser.py`
  - 문 통과 / 턴 / decision point 판정
- `python_server/app/state/cell_graph.py`
  - qualitative cell graph 저장
- `python_server/app/state/state_machine.py`
  - FSM 상태 전이

즉, Unity가 보내는 JSON 프레임을 Python이 받아서 처리하고, 결과를 다시 Unity로 보내는 구조입니다.

---

## 10. Python 서버 실행

가상환경이 켜진 상태에서 `python_server/` 폴더 안에서 실행합니다.

```bash
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

정상 실행되면 대략 이런 의미입니다.

- `http://127.0.0.1:8000` 에 HTTP 서버가 뜸
- `ws://127.0.0.1:8000/ws/runtime` 에 WebSocket이 뜸
- Unity가 여기로 접속 가능

브라우저 또는 `curl`로 확인해도 됩니다.

```bash
curl http://127.0.0.1:8000/
```

세션 상태 확인:

```bash
curl http://127.0.0.1:8000/session/status
```

---

## 11. Unity 설치

### 11.1 Unity Hub 설치

Unity Hub를 설치합니다.

### 11.2 Unity Editor 설치

Unity Hub에서 **Unity 6.x** 버전을 설치합니다.

권장 모듈:

- Microsoft Visual Studio Community 또는 외부 C# IDE 연동
- Windows Build Support / Mac Build Support (필요 시)

---

## 12. Unity 프로젝트 열기

### 방법 1: 이 저장소를 Unity 프로젝트 루트로 사용

Unity Hub에서 **Add** 또는 **Open**을 눌러 현재 저장소 루트를 선택합니다.

즉, 아래 폴더를 그대로 프로젝트로 엽니다.

```text
Egocentric-Cell-Graph-Memory-for-SmartGlass/
```

### 방법 2: 빈 3D 프로젝트 만든 뒤 파일 복사

이미 다른 Unity 프로젝트가 있다면, 이 저장소의 아래 폴더를 복사해도 됩니다.

- `Assets/`

하지만 가장 단순한 방법은 **이 저장소 자체를 Unity 프로젝트처럼 여는 것**입니다.

---

## 13. Unity에서 폴더 구조 확인

Unity에서 `Assets/` 아래에 대략 아래가 보여야 합니다.

```text
Assets/
  Scripts/
    Sensor/
    Network/
    UI/
    Player/
    Debug/
  Scenes/
  Prefabs/
  Materials/
  Resources/
```

현재 저장소에는 `.unity` 바이너리 씬 파일 대신, 씬 구성 문서가 들어 있습니다.

- `Assets/Scenes/DemoIndoorScene.md`

즉, 씬은 Unity Editor 안에서 직접 만들어야 합니다.

---

## 14. DemoIndoorScene 만들기

### 14.1 새 씬 만들기

Unity에서 새 3D 씬을 만듭니다.

이름을 다음처럼 저장합니다.

```text
Assets/Scenes/DemoIndoorScene.unity
```

### 14.2 씬에 기본 오브젝트 만들기

아래 오브젝트를 배치합니다.

- Directional Light
- 바닥(Floor)
- 벽(Walls)
- 복도 구간
- 방(Room)
- 문(Door) 오브젝트
- 갈림길 / decision area
- 작은 open space

실제 그래픽이 화려할 필요는 없습니다.
처음에는 큐브/Plane만으로도 테스트 가능합니다.

---

## 15. PlayerRig 만들기

### 15.1 루트 오브젝트 생성

빈 GameObject를 만들고 이름을 `PlayerRig`로 지정합니다.

### 15.2 컴포넌트 추가

`PlayerRig`에 아래를 붙입니다.

- `CharacterController`
- `PlayerController`
- `ImuSimulator`
- `SensorCapture`
- `PythonBridge`

### 15.3 카메라 추가

`PlayerRig`의 자식으로 `Main Camera`를 넣습니다.

### 15.4 연결

- `PlayerController.playerCamera` → `Main Camera`
- `ImuSimulator.yawSource` → `Main Camera` 또는 `PlayerRig`
- `SensorCapture.captureCamera` → `Main Camera`
- `PythonBridge.imuSimulator` → `PlayerRig`의 `ImuSimulator`
- `PythonBridge.sensorCapture` → `PlayerRig`의 `SensorCapture`

---

## 16. UI Canvas 만들기

### 16.1 Canvas 생성

씬에 `Canvas`를 추가합니다.

### 16.2 TextMeshPro 텍스트 추가

다음 텍스트를 각각 만듭니다.

- Instruction Text
- Cell ID Text
- Cell Type Text
- Event Text
- Status Text
- Metrics Text
- Graph Summary Text

### 16.3 버튼 추가

버튼 4개를 만듭니다.

- Start Session
- Reset Session
- Stop Session
- Backtrack

### 16.4 스크립트 연결

적당한 GameObject(예: `UIRoot`)에 아래 스크립트를 붙입니다.

- `NavigationUI`
- `DebugGraphView`
- `SessionController`

그리고 Inspector에서 참조를 연결합니다.

#### NavigationUI 연결
- `pythonBridge` → PlayerRig의 `PythonBridge`
- `instructionText` → Instruction Text
- `cellIdText` → Cell ID Text
- `cellTypeText` → Cell Type Text
- `eventText` → Event Text
- `statusText` → Status Text
- `metricsText` → Metrics Text

#### DebugGraphView 연결
- `pythonBridge` → PlayerRig의 `PythonBridge`
- `graphSummaryText` → Graph Summary Text

#### SessionController 연결
- `pythonBridge` → PlayerRig의 `PythonBridge`

### 16.5 버튼 OnClick 연결

각 버튼의 `OnClick()`에 `SessionController` 메서드를 연결합니다.

- Start Session 버튼 → `SessionController.StartSession()`
- Reset Session 버튼 → `SessionController.ResetSession()`
- Stop Session 버튼 → `SessionController.StopSession()`
- Backtrack 버튼 → `SessionController.TriggerBacktracking()`

---

## 17. Unity 스크립트가 각각 무슨 역할인지

### 17.1 `PlayerController.cs`
- WASD 이동
- 마우스 시점 회전
- 1인칭 이동 테스트

### 17.2 `ImuSimulator.cs`
- 현재 yaw 계산
- yaw smoothing
- yaw delta 계산
- 누적 turn 계산

### 17.3 `SensorCapture.cs`
- 카메라 화면을 캡처
- `AsyncGPUReadback`으로 GPU → CPU 복사
- JPG 인코딩
- PythonBridge로 전달

### 17.4 `PythonBridge.cs`
- HTTP 세션 시작/리셋/종료
- WebSocket 연결
- Unity → Python 프레임 전송
- Python → Unity 결과 수신

### 17.5 `NavigationUI.cs`
- instruction 표시
- cell id / cell type 표시
- event/confidence 표시
- status 표시

### 17.6 `DebugGraphView.cs`
- graph summary 표시
- FSM 상태 표시

### 17.7 `SessionController.cs`
- 버튼에서 PythonBridge 호출

---

## 18. Python 서버와 Unity를 동시에 실행하는 순서

실제로는 **항상 Python 서버를 먼저 켜고**, 그 다음 Unity를 실행하는 것이 편합니다.

권장 순서:

1. 터미널 열기
2. `python_server/`로 이동
3. 가상환경 활성화
4. `uvicorn app.server:app --host 127.0.0.1 --port 8000` 실행
5. Unity Editor에서 프로젝트 열기
6. `DemoIndoorScene` 열기
7. Play 버튼 누르기
8. UI에서 Start Session 클릭

---

## 19. 세션 제어 API가 실제로 하는 일

### 19.1 Start Session
Unity가 다음 HTTP를 호출합니다.

- `POST /session/start`

이후 WebSocket 연결을 열고 프레임 스트리밍을 시작합니다.

### 19.2 Reset Session
Unity가 다음 HTTP를 호출합니다.

- `POST /session/reset`

현재 세션 상태, 셀 그래프, 프레임 카운터 등을 초기화하는 용도입니다.

### 19.3 Stop Session
Unity가 다음 HTTP를 호출합니다.

- `POST /session/stop`

세션을 종료하고, Python 쪽 결과를 파일로 내보냅니다.

### 19.4 Backtrack
Unity가 다음 HTTP를 호출합니다.

- `POST /session/backtrack`

Python이 이미 지나온 edge를 역순으로 따라가며 안내 문구를 보냅니다.

---

## 20. 데이터가 실제로 어떻게 오가는지

### 20.1 Unity → Python 프레임 패킷

Unity는 대략 이런 JSON을 보냅니다.

```json
{
  "session_id": "demo_001",
  "frame_id": 1024,
  "timestamp": 123.456,
  "yaw_deg": 87.2,
  "step_count": 54,
  "jpg_b64": "<base64_jpg_bytes>"
}
```

### 20.2 Python → Unity 결과 패킷

Python은 대략 이런 JSON을 돌려줍니다.

```json
{
  "frame_id": 1024,
  "fsm_state": "IN_CELL",
  "cell_id": 7,
  "cell_type": "corridor_segment",
  "event": "turn_right",
  "instruction": "오른쪽으로 도세요",
  "confidence": 0.91,
  "graph_summary": {
    "num_cells": 8,
    "num_edges": 7
  }
}
```

실제 예시는 아래 파일도 참고하세요.

- `python_server/example_packets/frame_packet.json`
- `python_server/example_packets/result_packet.json`

---

## 21. 첫 실행 테스트 방법

가장 간단한 테스트 순서는 아래입니다.

### 단계 1
Python 서버 실행:

```bash
cd python_server
source .venv/bin/activate   # Windows는 Activate.ps1
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

### 단계 2
Unity에서 `DemoIndoorScene` 열기

### 단계 3
Play 버튼 클릭

### 단계 4
Start Session 버튼 클릭

### 단계 5
WASD + 마우스로 이동

### 단계 6
UI 텍스트가 바뀌는지 확인

확인 항목:

- Status가 `Connected`로 바뀌는지
- Cell ID가 업데이트되는지
- Event/Confidence가 바뀌는지
- Graph summary가 업데이트되는지

### 단계 7
문 쪽으로 이동해보고, 갈림길도 지나가 봅니다.

### 단계 8
Backtrack 버튼 클릭

이후 아래 같은 안내가 오는지 봅니다.

- `왼쪽으로 도세요`
- `오른쪽으로 도세요`
- `앞 문으로 나가세요`
- `왼쪽 벽의 문으로 나가세요`
- `복도를 따라 직진하세요`

---

## 22. 결과 파일은 어디에 저장되는가

세션 종료 후 Python 쪽에서 아래 경로에 결과를 저장합니다.

```text
python_server/outputs/{session_id}/
```

예:

```text
python_server/outputs/demo_001/
```

여기 들어갈 수 있는 파일:

- `graph.json`
- `events.jsonl`
- `results.jsonl`
- 향후 debug frame / video 확장 가능

---

## 23. graph.json은 뭘 보는 파일인가

`graph.json`은 지금까지 생성된 cell/edge를 저장합니다.

여기서 확인할 수 있는 것:

- 셀 개수
- edge 개수
- 각 셀의 타입
- entry heading
- observed door side
- landmark token
- transition type
- exit side
- step count

즉, “어떤 복도 → 어떤 방 → 어떤 갈림길” 순서로 이동했는지 정성적으로 볼 수 있습니다.

---

## 24. 이 프로젝트에서 절대 헷갈리면 안 되는 점

이 프로젝트는 **scene label이 바뀌었다고 해서 무조건 새 cell을 만들지 않습니다.**

새 cell은 다음 같은 경우에만 만듭니다.

- confirmed door pass
- strong turn
- confirmed decision point
- confirmed scene type change + 최소 거리 + cooldown 조건 만족

즉, 단순한 장면 유사도 변화만으로 분할하지 않는 것이 핵심입니다.

---

## 25. 처음 하는 사람이 많이 막히는 포인트

### 25.1 `fastapi` 또는 패키지 import 에러
가상환경이 켜져 있는지 확인하세요.

```bash
which python
pip list
```

Windows PowerShell이면:

```powershell
Get-Command python
pip list
```

### 25.2 Unity에서 버튼 눌러도 반응 없음
보통 아래 중 하나입니다.

- Python 서버가 안 켜짐
- `PythonBridge` 참조 연결 안 됨
- 버튼 `OnClick()` 연결 안 됨
- 포트(`8000`)가 다름

### 25.3 Unity가 연결은 되는데 결과가 안 옴
점검 순서:

1. Python 서버 콘솔에 에러가 있는지 확인
2. WebSocket 주소가 `ws://127.0.0.1:8000/ws/runtime` 인지 확인
3. `Start Session`을 눌렀는지 확인
4. `SensorCapture.captureCamera` 참조가 비어 있지 않은지 확인
5. `PythonBridge.sensorCapture`, `imuSimulator` 참조가 연결되어 있는지 확인

### 25.4 Unity Play 중 NullReferenceException
Inspector에서 대부분 참조 연결이 빠진 것입니다.

특히 확인:

- `PlayerController.playerCamera`
- `SensorCapture.captureCamera`
- `PythonBridge.imuSimulator`
- `PythonBridge.sensorCapture`
- `NavigationUI` 텍스트 참조들
- `DebugGraphView.graphSummaryText`

### 25.5 PyTorch 설치가 너무 무겁다
지금 저장소 구조는 **모델이 없어도 fallback heuristic**으로 최소 데모가 가능하도록 만들어져 있습니다.
따라서 처음에는 서버만 띄우고, 이후에 모델을 붙여도 됩니다.

---

## 26. 추천 디버깅 순서

처음부터 모든 걸 한 번에 보지 말고 아래 순서로 확인하세요.

### 1단계: HTTP 서버만 확인

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/session/status
```

### 2단계: Unity에서 Start Session만 확인
- 버튼 누를 때 에러가 없는지
- 상태 텍스트가 바뀌는지

### 3단계: 프레임 전송 확인
- `Sent` 숫자가 증가하는지
- `Dropped`가 너무 높지 않은지

### 4단계: Python 결과 수신 확인
- Event / Cell ID / Graph Summary가 바뀌는지

### 5단계: Backtrack 확인
- Backtrack 버튼 클릭 후 안내 문구가 역방향으로 바뀌는지

---

## 27. 향후 모델 붙이는 방법

현재 구현은 구조를 먼저 잡아 둔 상태입니다.
나중에 실제 모델을 넣으려면 아래 모듈을 교체/확장하면 됩니다.

- detector: `python_server/app/vision/detector_frontend.py`
- tracker: `python_server/app/vision/tracker_frontend.py`
- scene classifier: `python_server/app/vision/scene_classifier.py`
- VLM arbiter: `python_server/app/vision/vlm_arbiter.py`

즉, 통신 프로토콜은 유지하고 내부 인식기만 교체하면 됩니다.

---

## 28. 실행 예시: 가장 추천하는 실제 루틴

아래 순서대로 하면 됩니다.

### 터미널 1

```bash
cd Egocentric-Cell-Graph-Memory-for-SmartGlass/python_server
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.server:app --host 127.0.0.1 --port 8000
```

### Unity Editor

1. 프로젝트 열기
2. `Assets/Scenes/DemoIndoorScene.unity` 열기
3. `PlayerRig`, `Main Camera`, `Canvas`, 버튼, 텍스트 연결 확인
4. Play 클릭
5. Start Session 클릭
6. 움직이기
7. Backtrack 클릭
8. Stop Session 클릭

### 결과 확인

```bash
cd Egocentric-Cell-Graph-Memory-for-SmartGlass
find python_server/outputs -maxdepth 3 -type f
```

---

## 29. 꼭 기억할 체크리스트

실행 전 체크:

- [ ] Python 3.11 설치됨
- [ ] 가상환경 생성됨
- [ ] `pip install -r requirements.txt` 완료
- [ ] `uvicorn app.server:app --host 127.0.0.1 --port 8000` 실행 중
- [ ] Unity 프로젝트 열림
- [ ] `PlayerRig` 구성 완료
- [ ] `Main Camera` 연결 완료
- [ ] `SensorCapture` 연결 완료
- [ ] `PythonBridge` 참조 연결 완료
- [ ] UI 텍스트 연결 완료
- [ ] 버튼 `OnClick()` 연결 완료

실행 중 체크:

- [ ] Status가 Connected
- [ ] Sent frame count 증가
- [ ] Event/Confidence 업데이트
- [ ] Cell ID / Cell Type 업데이트
- [ ] Graph Summary 업데이트

종료 후 체크:

- [ ] `python_server/outputs/{session_id}/graph.json` 생성
- [ ] `events.jsonl` 생성
- [ ] `results.jsonl` 생성

---

## 30. 마지막으로: 가장 쉬운 한 줄 요약

**Python 서버를 먼저 띄우고, Unity 씬에서 `PlayerRig + Camera + SensorCapture + PythonBridge + UI`를 연결한 뒤, Play 후 Start Session을 누르고 이동하면 됩니다. 마지막에 Backtrack을 누르면 역방향 안내가 나옵니다.**

필요하면 다음 단계로도 확장할 수 있습니다.

- 실제 YOLO11n weight 연결
- 실제 ByteTrack 연결
- MobileOne-S1 분류기 연결
- VLM arbitration 고도화
- Unity 실내 환경 고도화

