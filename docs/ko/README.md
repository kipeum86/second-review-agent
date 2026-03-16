언어: [English](../../README.md) | **한국어**

# 10년차 파트너 변호사 반성문

AI가 만든 법률 문서, 내보내기 전에 한 번 더 잡는 최종 검토 에이전트. Claude Code 기반.

> **[면책조항](disclaimer.md)** | **[Disclaimer](../en/disclaimer.md)**

## 개요

`10년차 파트너 변호사 반성문`은 법무법인 진주의 최종 검토 에이전트입니다. 고덕수 변호사([contract-review](https://github.com/kipeum86/contract-review-agent)), 한석봉 변호사([legal-writing](https://github.com/kipeum86/legal-writing-agent)), 김재식 변호사([general-legal-research](https://github.com/kipeum86/general-legal-research)), 심진주 변호사([game-legal-research](https://github.com/kipeum86/game-legal-research-agent))가 만든 문서를 받아서 인용을 검증하고, 논리를 따지고, 문장을 다듬고, 레드라인 DOCX로 결과를 냅니다. 문서가 밖으로 나가기 전 마지막 관문입니다.

페르소나는 **10년차 파트너 변호사 반성문** — AI가 만든 문서를 본능적으로 의심하는 자칭 AI 러다이트. 덕분에 사무소에서 가장 집요하게 검증합니다. 여백에 빨간펜, 한 줄 코멘트, 가짜 판례에는 무관용.

이 프로젝트는 법률 자문이 **아닙니다**. AI 산출물의 품질 관리를 돕는 도구입니다.

## 설계 원칙

- **리뷰도 틀리면 안 된다**: 리뷰 과정에서 환각을 만들지 않는 게 핵심. "없는 판례"라고 단정하려면 진짜 없다는 증거가 있어야 하고, 애매하면 "확인 불가"로 둠
- **검토만 한다, 직접 쓰지 않는다**: 새로운 판례를 찾아주거나 분석 구조를 바꾸는 건 월권. 확인하고 지적하는 것까지만
- **릴리스 판단은 따로**: 점수가 높아도 치명적 문제가 하나 있으면 발송 불가. 점수와 릴리스 권고는 별개
- **수정은 반드시 추적 변경으로**: DOCX 추적 변경 + 여백 코멘트로만 수정. 몰래 고치는 건 금지
- **인용 검증은 원본 DB에서**: law.go.kr, 대법원 종합법률정보, congress.gov, eur-lex.europa.eu 등 1차 법률 DB 직접 대조

## 워크플로우

| 명령어 | 워크플로우 | 설명 |
|--------|-----------|------|
| `/review` | WF1 — 단일 문서 검토 | 8단계 파이프라인: 파싱 → 인용 검증 → 실체/작성/구조/서식 리뷰 → 점수 → 레드라인 → 자체 검증 |
| `/cross-review` | WF2 — 교차 검토 | 관련 문서끼리 사실·용어·날짜가 맞는지 비교 |
| `/rereview` | WF3 — 재검토 | 수정본이 이전 지적사항을 제대로 반영했는지 확인 |
| `/library` | WF4 — 라이브러리 관리 | 샘플, 체크리스트, 반복 이슈, 스타일 프로필 관리 |

### WF1: 단일 문서 검토 (8단계)

| 단계 | 이름 | 사용 스킬 | 산출물 |
|------|------|----------|--------|
| 1 | 접수 | — | `review-manifest.json` |
| 2 | 파싱 | `document-parser` | `parsed-structure.json`, `citation-list.json`, `defined-terms.json` |
| 3 | 인용 검증 | `citation-checker` (서브에이전트) | `verification-audit.json` |
| 4 | 내용 리뷰 | `substance-reviewer`, `writing-quality-reviewer`, `structure-checker` | 차원 2~5 findings |
| 5 | 서식 리뷰 | `formatting-reviewer` | 차원 6 findings |
| 6 | 종합·점수 | `scoring-engine`, `known-issues-manager` | `issue-registry.json`, `review-scorecard.json` |
| 7 | 결과물 생성 | `redline-generator`, `cover-memo-writer` | 레드라인 DOCX, 클린 DOCX, 커버 메모 |
| 8 | 자체 검증 | `quality-gate` | 7항목 검증 보고서 |

단계마다 `output/{matter_id}/checkpoint.json`에 진행 상태를 저장합니다. 중간에 끊겨도 이어서 할 수 있습니다.

## 7개 검토 차원

| # | 차원 | 뭘 보는가 |
|---|------|----------|
| 1 | 인용·사실 검증 | 인용한 법령·판례가 실제로 있는가? 조항 번호가 맞는가? 주장을 뒷받침하는가? |
| 2 | 법률 논리 | 논리 전개가 탄탄한가? 비약은 없는가? 반대 논거를 다뤘는가? |
| 3 | 의뢰인 니즈 부합 | 의뢰인이 물어본 것에 답했는가? 실무적으로 써먹을 수 있는가? |
| 4 | 문장 품질 | 격식체 일관성, 용어 통일, 번역투 여부, 스타일 편차 |
| 5 | 구조 | 번호 연속성, 교차참조 유효성, 정의 용어 일관성 |
| 6 | 서식·외관 | 글꼴·크기 통일, 제목 체계, 여백, 전반적 깔끔함 |
| 7 | 문서 간 일관성 | (WF2 전용) 관련 문서끼리 사실·용어·날짜가 어긋나지 않는지 |

## 인용 검증 분류

| 상태 | 하위 상태 | 의미 |
|------|----------|------|
| **Verified** | — | 있고, 조항 번호 맞고, 주장도 뒷받침함 |
| **Issue** | Nonexistent | 진짜 없음 (DB 검색 완료, 형식도 이상) |
| | Wrong_Pinpoint | 법령은 있는데 조항 번호가 틀림 |
| | Unsupported_Proposition | 법령은 있는데 그 주장을 뒷받침하지 않음 |
| | Wrong_Jurisdiction | 엉뚱한 관할의 법령을 인용 |
| | Stale | 이미 개정되었거나 폐지됨 |
| | Translation_Mismatch | 번역이 원문과 심하게 다름 |
| **Unverifiable** | No_Access | DB 접근이 안 됨 (유료, 서버 장애 등) |
| | Secondary_Only | 2차 자료에서만 확인되고 원본은 못 봄 |
| | No_Evidence | 검색했는데 있는지 없는지 판단이 안 됨 |

**핵심 규칙**: "없다"고 단정(`Nonexistent`)하려면 **정말 없다는 증거**가 있어야 합니다. 애매하면 `Unverifiable_No_Evidence`로 둡니다.

## 점수와 릴리스 판단

**차원별 점수**: 1~10점 (10 = 문제 없음, 1~3 = 치명적 이슈 있음)

**종합 등급**: A (평균 8.5 이상), B (7.0 이상), C (5.0 이상), D (5.0 미만)

**릴리스 권고** (점수와 별개로 판단):

| 권고 | 조건 |
|------|------|
| Release Not Recommended | 차원 1~3에서 Critical 발견, 또는 핵심 결론에 가짜 인용 |
| Manual Review Required | 핵심 결론에 확인 불가 인용, 또는 차원 2에서 Major 2건 이상 |
| Pass with Warnings | Major는 있지만 차원 1~3에 Critical은 없음, 또는 B등급 미만 |
| Pass | Critical·Major 없음, B등급 이상 |

## 산출물

리뷰가 끝나면 3개 파일이 나옵니다:

| 산출물 | 설명 |
|--------|------|
| **레드라인 DOCX** | 원본에 추적 변경 + 여백 코멘트를 단 파일. 뭘 고쳤고 왜 고쳤는지 다 보임 |
| **클린 DOCX** | Critical·Major 수정만 반영한 깨끗한 버전. 추적 변경·코멘트 없음 |
| **커버 메모** | 10개 섹션짜리 검토 보고서: 릴리스 권고, 점수표, 지적사항, 반복 패턴, 스타일 분석, 다음 할 일 |

## 라이브러리

| 디렉토리 | 용도 | 관리 방법 |
|----------|------|----------|
| `library/checklists/` | 문서 유형별 체크리스트 (YAML) | `/library add-checklist` |
| `library/known-issues/` | 주니어 에이전트별 반복 실수 패턴 (JSON) | 3회 이상 반복되면 자동 제안 |
| `library/samples/` | 스타일 비교용 작성 샘플 | `/library add-sample` |
| `library/style-profiles/` | 샘플에서 뽑아낸 스타일 프로필 | `/library style-profile regenerate` |

기본 체크리스트 6종 포함: 법률의견서(한/영), 리서치 리포트, 소송서면, 계약검토 보고서, 범용.

## 사용법

### 준비물

- [Claude Code](https://claude.ai/code) CLI 설치 및 인증
- Python 3 + `python-docx`: `pip install python-docx`
- MCP 검색 서비스 (brave-search, tavily) — 인용 검증에 쓰며, 없어도 되지만 있으면 좋음

### 실행

1. 이 저장소를 클론하고 Claude Code에서 열기
2. `input/`에 DOCX 파일 넣기
3. `/review` 또는 "이거 검토해줘" 입력
4. 8단계 파이프라인 돌아가고 `output/`에 결과물 생성
5. 중간에 끊기면 마지막 체크포인트에서 이어서 진행

**예시:**

```text
input/ 에 있는 법률의견서 검토해줘. 정밀검토로.
```

```text
/cross-review — input/ 에 리서치 리포트랑 법률의견서 두 개 있어. 교차검토 해줘.
```

```text
/rereview — 수정본 올렸어. 이전 라운드 피드백 반영 확인해줘.
```

## 관련 프로젝트

이 에이전트가 검토하는 주니어 에이전트들:

| 담당 변호사 | 에이전트 | 하는 일 |
|------------|----------|--------|
| 고덕수 변호사 | [contract-review-agent](https://github.com/kipeum86/contract-review-agent) | 계약서 분석, 리스크 식별 |
| 한석봉 변호사 | [legal-writing-agent](https://github.com/kipeum86/legal-writing-agent) | 법률 문서 작성 |
| 김재식 변호사 | [general-legal-research](https://github.com/kipeum86/general-legal-research) | 다관할권 법률 리서치 |
| 심진주 변호사 | [game-legal-research-agent](https://github.com/kipeum86/game-legal-research-agent) | 게임 산업 규제 리서치 |

## 면책조항

법률 문서 품질 관리용 도구입니다. 법률 자문이 아닙니다. 법률적 판단이 필요하면 해당 관할권 변호사에게 상담하세요. 전체 [면책조항](disclaimer.md) 참고.

## 라이선스

MIT. `LICENSE` 참조.
