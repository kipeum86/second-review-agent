언어: [English](../../README.md) | **한국어**

# 10년차 파트너 변호사 반성문

AI가 생성한 법률 문서의 최종 품질 게이트. Claude Code 기반.

> **[면책조항](disclaimer.md)** | **[Disclaimer](../en/disclaimer.md)**

## 개요

`10년차 파트너 변호사 반성문`은 법무법인 진주에서 법률 문서가 외부로 발송되기 전 최종 검토를 수행하는 Claude Code 에이전트입니다. 4개 주니어 변호사 에이전트([contract-review](https://github.com/kipeum86/contract-review-agent), [legal-writing](https://github.com/kipeum86/legal-writing-agent), [general-legal-research](https://github.com/kipeum86/general-legal-research), [game-legal-research](https://github.com/kipeum86/game-legal-research-agent))가 작성한 문서의 인용 검증, 법률 논리 점검, 작성 품질 평가를 수행하고, 추적 변경이 적용된 레드라인 DOCX를 생성합니다.

에이전트 페르소나는 **주홍철 파트너** — 자칭 AI 러다이트(Luddite)로, AI가 생성한 법률 문서를 근본적으로 불신합니다. 덕분에 사무소에서 가장 집요한 검증자입니다. 리뷰 스타일: 여백에 빨간펜, 한 줄 코멘트, 환각 인용에 대한 무관용.

이 프로젝트는 법률 자문을 제공하지 **않습니다**. AI 생성 법률 산출물의 품질 관리를 보조합니다.

## 핵심 설계 원칙

- **리뷰의 반환각(Anti-hallucination)**: 리뷰어 자체가 환각을 만들어서는 안 됨. `Nonexistent` 분류에는 부존재의 적극적 증거가 필요하며, 불확실하면 `Unverifiable`로 분류
- **검증만, 작성은 안 함**: 에이전트는 확인하고 비평함 — 새로운 법률 근거를 제시하거나, 분석 구조를 재설계하거나, 법률 자문을 하지 않음
- **독립적 릴리스 게이트**: 릴리스 권고(Pass / Pass with Warnings / Manual Review Required / Release Not Recommended)는 등급과 독립된 안전 게이트
- **추적 변경만 사용**: 모든 수정은 DOCX 추적 변경 + 여백 코멘트로 수행. 무단 수정 금지
- **관할권 인식 인용 검증**: 1차 법률 DB 대비 검증 (law.go.kr, congress.gov, eur-lex.europa.eu 등)

## 워크플로우

| 명령어 | 워크플로우 | 설명 |
|--------|-----------|------|
| `/review` | WF1 — 단일 문서 검토 | 8단계 파이프라인: 파싱, 인용 검증, 실체/작성/구조/서식 리뷰, 점수 산정, 레드라인 생성, 자체 검증 |
| `/cross-review` | WF2 — 교차 문서 검토 | 관련 문서 간 사실/용어/날짜 일관성 비교 |
| `/rereview` | WF3 — 재검토 | 수정본을 이전 라운드 findings 대비 확인 |
| `/library` | WF4 — 라이브러리 관리 | 작성 샘플, 체크리스트, 알려진 이슈 패턴, 스타일 프로필 관리 |

### WF1: 단일 문서 검토 (8단계)

| 단계 | 이름 | 스킬 | 산출물 |
|------|------|------|--------|
| 1 | 접수 | — | `review-manifest.json` |
| 2 | 파싱 | `document-parser` | `parsed-structure.json`, `citation-list.json`, `defined-terms.json` |
| 3 | 인용 검증 | `citation-checker` (서브에이전트 경유) | `verification-audit.json` |
| 4 | 실체 리뷰 | `substance-reviewer`, `writing-quality-reviewer`, `structure-checker` | Dim 2-5 findings |
| 5 | 서식 리뷰 | `formatting-reviewer` | Dim 6 findings |
| 6 | 통합 및 점수 산정 | `scoring-engine`, `known-issues-manager` | `issue-registry.json`, `review-scorecard.json` |
| 7 | 산출물 생성 | `redline-generator`, `cover-memo-writer` | 레드라인 DOCX, 클린 DOCX, 커버 메모 |
| 8 | 자체 검증 | `quality-gate` | 7항목 검증 보고서 |

매 단계 완료 후 `output/{matter_id}/checkpoint.json`에 상태가 저장됩니다. 중단된 세션은 자동으로 재개됩니다.

## 7개 리뷰 차원

| # | 차원 | 검토 대상 |
|---|------|----------|
| 1 | 인용 및 사실 검증 | 인용된 법령/판례가 실존하는가? 조항 번호가 정확한가? 주장을 뒷받침하는가? |
| 2 | 법률 실체 및 논리 | 추론이 건전한가? 논리적 비약은 없는가? 반대논거를 다뤘는가? |
| 3 | 의뢰인 정렬 | 실제 질문에 답했는가? 실무적 함의가 포함되었는가? |
| 4 | 작성 품질 | 격식체 일관성, 용어 통일, 번역투 탐지, 스타일 지문 |
| 5 | 구조적 무결성 | 번호 연속성, 교차참조 유효성, 정의 용어 일관성 |
| 6 | 서식 및 외관 | 글꼴/크기 일관성, 제목 계층, 여백 균일성, 전문적 외관 |
| 7 | 교차 문서 일관성 | (WF2 전용) 관련 문서 간 사실/용어/날짜 일관성 |

## 인용 검증 분류 체계

| 상태 | 하위 상태 | 의미 |
|------|----------|------|
| **Verified** | — | 법령/판례가 존재하며 주장을 뒷받침 |
| **Issue** | Nonexistent | 부존재의 적극적 증거 확보 |
| | Wrong_Pinpoint | 법령은 존재하나 조항 번호 오류 |
| | Unsupported_Proposition | 법령은 존재하나 주장을 뒷받침하지 않음 |
| | Wrong_Jurisdiction | 다른 관할권의 법령 |
| | Stale | 개정 또는 폐지된 법령 |
| | Translation_Mismatch | 번역이 원문과 실질적으로 괴리 |
| **Unverifiable** | No_Access | 1차 법률 DB 접근 불가 |
| | Secondary_Only | 2차 자료만 존재를 확인 |
| | No_Evidence | 검색 결과 불충분 — 확인도 부인도 안 됨 |

**핵심 규칙**: `Nonexistent`에는 **부존재의 적극적 증거**가 필요합니다. 불확실하면 반드시 `Unverifiable_No_Evidence`로 분류합니다.

## 점수 산정 및 릴리스

**차원별 점수**: 1-10 척도 (10 = 이슈 없음, 1-3 = 크리티컬 발견)

**종합 등급**: A (평균 >= 8.5), B (>= 7.0), C (>= 5.0), D (< 5.0)

**릴리스 권고** (독립적 안전 게이트):

| 권고 | 조건 |
|------|------|
| Release Not Recommended | Dim 1-3 Critical 발견; 또는 핵심 결론에 Nonexistent 인용 |
| Manual Review Required | 주요 결론에 Unverifiable 인용; 또는 Dim 2에 Major >= 2건 |
| Pass with Warnings | Major 존재하나 Dim 1-3 Critical 없음; 또는 등급 < B |
| Pass | Critical/Major 없음; 등급 >= B |

## 산출물

각 리뷰는 3개 파일을 생성합니다:

| 산출물 | 설명 |
|--------|------|
| **레드라인 DOCX** | 추적 변경(`<w:del>/<w:ins>`) + 심각도별 여백 코멘트가 적용된 원본. 저자: "주홍철 파트너" |
| **클린 DOCX** | Critical/Major 텍스트 수정만 수락한 깨끗한 문서. 추적 변경 및 코멘트 없음 |
| **커버 메모** | 10개 섹션 리뷰 보고서: 릴리스 권고(최상단), 스코어카드, 심각도별 findings, 반복 패턴, 스타일 분석, 권장 다음 단계 |

## 라이브러리 시스템

| 디렉토리 | 용도 | 관리 방법 |
|----------|------|----------|
| `library/checklists/` | 문서 유형별 체크리스트 (YAML) | `/library add-checklist` |
| `library/known-issues/` | 주니어 에이전트별 반복 패턴 (JSON) | 3회 이상 발생 시 자동 제안 |
| `library/samples/` | 스타일 지문용 작성 샘플 | `/library add-sample` |
| `library/style-profiles/` | 집계된 스타일 프로필 | `/library style-profile regenerate` |

기본 체크리스트 6개 포함: 법률의견서(한/영), 리서치 리포트, 소송서면, 계약검토 보고서, 범용.

## 사용 방법

### 요구사항

- [Claude Code](https://claude.ai/code) CLI 설치 및 인증
- Python 3 + `python-docx`: `pip install python-docx`
- MCP 검색 서비스 (brave-search, tavily) — 인용 검증용, 선택사항이나 권장

### 리뷰 실행

1. 이 저장소를 클론하고 Claude Code에서 디렉토리를 엽니다.
2. `input/`에 DOCX 파일을 넣습니다.
3. `/review` 또는 "이거 검토해줘"라고 입력합니다.
4. 에이전트가 8단계 파이프라인을 실행하고 `output/`에 산출물을 생성합니다.
5. 중단된 세션은 마지막 체크포인트에서 자동 재개됩니다.

**예시 프롬프트:**

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

이 에이전트는 아래 에이전트들이 작성한 문서를 최종 검토합니다:

| 에이전트 | 용도 |
|----------|------|
| [contract-review-agent](https://github.com/kipeum86/contract-review-agent) | 계약서 분석 및 리스크 식별 |
| [legal-writing-agent](https://github.com/kipeum86/legal-writing-agent) | 법률 문서 작성 |
| [general-legal-research](https://github.com/kipeum86/general-legal-research) | 다관할권 법률 리서치 |
| [game-legal-research-agent](https://github.com/kipeum86/game-legal-research-agent) | 게임 산업 규제 리서치 |

## 면책조항

이 프로젝트는 법률 문서 품질 관리 워크플로우를 지원합니다. 법률 자문을 제공하지 않습니다. 법률적 판단이 필요한 경우 해당 관할권의 자격을 갖춘 변호사에게 자문을 구하세요. 전체 [면책조항](disclaimer.md)을 확인하세요.

## 라이선스

MIT. `LICENSE` 참조.
