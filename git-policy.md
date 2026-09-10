# Git 운영 정책

이 문서는 지시문이다. Claude Code는 이 저장소에서 git을 다룰 때 아래 규칙을 그대로 따른다.
판단이 필요한 지점에서는 "덜 파괴적인 쪽"을 선택한다.

---

## 1. 원칙

1. 코드와 문서는 git으로 관리한다. 실험 산출물은 git이 아니라 **불변 디렉토리**로 누적한다.
2. 모든 실험 결과는 특정 commit 하나로 소급 가능해야 한다. 이것이 이 정책의 존재 이유다.
3. 이력을 지우는 조작은 하지 않는다. 잘못된 커밋은 되돌리되(revert), 다시 쓰지(rewrite) 않는다.

---

## 2. 브랜치

- 기본 브랜치는 `main` 하나다. 1인 프로젝트이므로 브랜치 전략을 만들지 않는다.
- 예외적으로 되돌릴 가능성이 큰 대규모 리팩터링만 `refactor/<주제>` 브랜치를 파고,
  완료 후 `--no-ff`로 병합한다.
- 사용자가 명시적으로 지시하지 않는 한 브랜치를 새로 만들지 않는다.

---

## 3. 커밋

### 3.1 형식

```
<type>(<scope>): <한 줄 요약> [<EXP-ID>]

<본문: 왜 이렇게 했는지. 무엇을 했는지는 diff가 말해준다>
```

- type: `feat` | `fix` | `exp` | `docs` | `refactor` | `test` | `chore`
- scope: `data` | `model` | `gating` | `eval` | `config` | `docs` 중 하나
- EXP-ID는 해당 실험과 관련된 변경일 때만 붙인다. 예: `feat(gating): 비대칭 임계값 구현 [EXP-005]`
- 요약은 한국어, 명령형이 아닌 서술형으로 쓴다.

### 3.2 단위

- 커밋 하나는 되돌렸을 때 의미가 온전한 단위여야 한다.
- 서로 무관한 변경을 한 커밋에 묶지 않는다. 특히 코드 수정과 문서 수정을 섞지 않는다.
- 포매팅/린트만 적용한 변경은 `chore(style):`로 분리한다.

### 3.3 커밋하지 않는 상황

- 테스트가 실패하는 상태로 커밋하지 않는다. 커밋 전에 `pytest -q`를 실행한다.
- 사용자에게 확인받지 않은 대규모 삭제는 커밋하지 않는다.

---

## 4. 실험과 git의 연동 — 가장 중요한 규칙

1. **실험 실행 전에 작업 트리가 깨끗해야 한다.** `git status`가 clean이 아니면 실행하지 않는다.
   커밋되지 않은 변경이 있으면 사용자에게 알리고 커밋을 먼저 제안한다.
2. 실행 시 `git rev-parse HEAD` 값을 `results/<EXP-ID>/metrics.json`의 `git_commit` 필드에 기록한다.
3. 실험이 완료되고 결과를 확인한 뒤 태그를 단다.

   ```bash
   git tag -a exp-003 -m "EXP-003 배제 공격군 신뢰도 분포 측정"
   ```
4. `results/<EXP-ID>/` 는 생성 후 수정하지 않는다. 재실행이 필요하면 `<EXP-ID>-r2` 로 새로 만든다.
5. 결과 해석이 바뀌어도 `metrics.json`을 고치지 않는다. 해석은 `experiments/` 쪽 스펙 문서에 쓴다.

Makefile의 `guard-clean` 타겟이 1번을 강제한다. 이 타겟을 우회하지 않는다.

---

## 5. 추적 대상

### 커밋한다

- `src/`, `configs/`, `tests/`, `scripts/`, `Makefile`, `pyproject.toml`
- `docs/` 전체 (결정 이력, 용어표, 원고)
- `experiments/` 전체 (실험 스펙, 대기열)
- `results/<EXP-ID>/metrics.json`, `results/<EXP-ID>/config.snapshot.yaml`
- 데이터셋 다운로드 스크립트와 SHA256 체크섬 파일

### 커밋하지 않는다

- `data/` 전체 (raw, interim, processed)
- `.venv/`, `__pycache__/`, `.ipynb_checkpoints/`
- `_sync/` (Windows 동기화용 임시 경로)
- 모델 바이너리, 100MB를 넘는 모든 파일

### 판단이 필요한 것

- `results/<EXP-ID>/figures/`: PNG 몇 장 수준이면 커밋한다. 수십 장 이상 누적되면
  사용자에게 제외를 제안하되, 스크립트로 재생성 가능함을 먼저 확인한다.
- `notebooks/`: 커밋하되 실행 출력은 지우고 커밋한다. 노트북에서 나온 수치를
  실험 결과로 인용하지 않는다.

---

## 6. 금지

1. `git push --force`, `git push -f` 를 실행하지 않는다.
2. `git rebase`, `git commit --amend`, `git reset --hard` 를 사용자 지시 없이 실행하지 않는다.
   특히 이미 push된 커밋에는 어떤 경우에도 사용하지 않는다.
3. `git clean -fd` 를 실행하지 않는다. 추적되지 않는 파일에 데이터가 있을 수 있다.
4. 코드 파일을 `train_v2.py`, `train_final.py` 식으로 복사해 버전을 만들지 않는다.
   코드의 버전은 git이 관리한다. 실험별 차이는 `configs/exp/` 로 표현한다.
5. `.gitignore`에 있는 항목을 `-f` 옵션으로 강제 추가하지 않는다.
6. 원격 저장소를 public으로 바꾸지 않는다. 데이터셋 라이선스와 미공개 원고가 포함되어 있다.
7. 커밋 메시지나 코드에 API 키, 토큰, 데이터셋 접근 자격증명을 넣지 않는다.

---

## 7. 되돌리기

- 잘못된 커밋: `git revert <hash>` 로 되돌리는 커밋을 새로 만든다.
- 특정 파일만 이전 상태로: `git restore --source=<hash> -- <path>`
- 어느 커밋에서 결과가 달라졌는지 추적: `git bisect` 를 쓰되, 실험 재실행 비용을
  사용자에게 먼저 알린다.

---

## 8. 자주 쓰는 조회

```bash
git log --oneline --graph -20              # 최근 이력
git log --grep=EXP-005                     # 특정 실험 관련 변경
git show exp-003                           # 해당 실험 시점의 코드 상태
git diff exp-002 exp-003 -- src/           # 두 실험 사이 코드 변경
```

---

## 9. Cowork와의 경계

- Cowork는 `experiments/`, `docs/` 만 수정한다. Claude Code는 이 두 경로를
  사용자 지시 없이 수정하지 않는다.
- 두 도구가 같은 파일을 건드려 충돌이 나면, 자동으로 해결하지 말고
  충돌 내용을 사용자에게 보고한다.
- Cowork 세션 전후로 `git status`를 확인한다. 예상치 못한 삭제가 있으면
  커밋하지 말고 먼저 보고한다.

---

## 10. 저장소 이전

향후 저장소를 Organization으로 옮길 수 있다. 이전 후 로컬에서 다음을 실행한다.

```bash
git remote set-url origin <새 URL>
git remote -v
```

이전 이후 개인 계정에 **같은 이름의 저장소를 새로 만들지 않는다.**
만들면 이전 URL의 자동 리다이렉트가 끊긴다.
