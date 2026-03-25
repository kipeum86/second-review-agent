---
name: ingest
description: >
  library/inbox/에 넣은 외부 참조 소스 파일(PDF, DOCX 등)을 자동으로
  Markdown 변환, Grade 판별, frontmatter 생성, 폴더 배치까지
  원스텝으로 처리한다. /ingest로 트리거.
---

# Source Ingest

`library/inbox/`에 파일을 넣고 `/ingest`를 실행하면 자동으로 처리한다.

## Trigger

- `/ingest` — inbox 전체 처리
- 사용자가 "소스 추가", "자료 넣었어", "ingest", "inbox" 등 요청 시

---

## Workflow

```
library/inbox/ 에 파일 드롭
  │
  ├─ Step 1: 파일 스캔
  ├─ Step 2: Markdown 변환
  ├─ Step 3: Grade 자동 판별
  ├─ Step 4: Frontmatter 생성
  ├─ Step 5: 목적 폴더로 이동
  └─ Step 6: 처리 결과 리포트
```

### Step 1: Inbox 스캔

```
inbox/ 내 모든 파일을 Glob으로 탐색
지원 포맷: .pdf, .docx, .pptx, .xlsx, .html, .md, .txt
비지원: .hwp, .hwpx → 유저에게 "PDF/DOCX 변환 후 다시 넣어주세요" 안내
```

- 파일이 0개면 "inbox가 비어 있습니다" 안내 후 종료
- 하위 폴더 안의 파일도 재귀 탐색
- `_processed/`, `_failed/` 내 파일은 스캔 대상에서 제외

### Step 2: Markdown 변환

| 입력 포맷 | 변환 방법 |
|----------|----------|
| `.pdf` | `mcp__markitdown__convert_to_markdown` (uri: `file:///절대경로`) |
| `.docx` | `mcp__markitdown__convert_to_markdown` |
| `.pptx`, `.xlsx`, `.html` | `mcp__markitdown__convert_to_markdown` |
| `.md`, `.txt` | 변환 불필요, 그대로 사용 |

**변환 실패 시:** 해당 파일을 `library/inbox/_failed/`로 이동 + 유저에게 실패 사유 안내

### Step 3: Grade 자동 판별

변환된 Markdown 내용을 분석하여 Grade를 판별한다.

#### 판별 규칙 (우선순위 순)

**Grade A — 공식 1차 소스 (법령, 공식 가이드라인):**

| 시그널 | 예시 |
|--------|------|
| 법률 번호 패턴 | `법률 제XXXXX호`, `대통령령 제XXXXX호`, `Act No. XXXX` |
| 고시/훈령 번호 패턴 | `고시 제XXXX-XXX호`, `훈령 제XXX호` |
| 출처 도메인 | law.go.kr, congress.gov, eur-lex.europa.eu, ecfr.gov |
| 발행 기관 | 정부 부처, 국회, 법제처, regulatory agency |
| 가이드라인 표지 패턴 | "안내서", "가이드라인", "해설서" + 정부 기관명 |
| 국제 조약/협약 | UN, WTO, WIPO 등 국제기구 공식 문서 |

**Grade B — 2차 소스 (판례, 실무 해설):**

| 시그널 | 예시 |
|--------|------|
| 판례 번호 | `대법원 20XXdaXXXXX`, `헌법재판소 20XX헌마XXX`, `No. XX-XXXX (circuit)` |
| 처분례/의결 번호 | `의결 제20XX-XXX-XXX호`, `시정명령` |
| 로펌 레터헤드/도메인 | kimchang.com, bkl.co.kr, leeko.com, skadden.com 등 |
| 뉴스레터/실무 해설 | "법률 뉴스레터", "Client Alert", "Legal Update" |
| 법조 칼럼 | 법률신문, 대한변호사협회, ABA Journal |

**Grade C — 학술/참고:**

| 시그널 | 예시 |
|--------|------|
| 학술지 형식 | 초록/Abstract, 참고문헌/References 섹션 |
| 학술 DB 출처 | KCI, RISS, SSRN, Google Scholar, HeinOnline |
| 저널명 패턴 | "법학연구", "정보법학", "Law Review", "Journal of" |
| 학위 논문 | 석사/박사 학위논문, thesis/dissertation |

**Grade D — 거부:**
- 뉴스 기사, AI 요약, 위키피디아, 블로그 → ingest 거부 + 안내:
  > "이 파일은 Grade D (비공식/비신뢰 소스)로 판별되어 라이브러리에 추가할 수 없습니다: `{filename}`"

**판별 불가:**
- 위 시그널이 어디에도 매칭되지 않으면 유저에게 질문:
  > "이 파일의 성격을 판별하지 못했습니다: `{filename}`
  > 내용 일부: {첫 200자}
  > Grade를 지정해주세요: A (법령/공식), B (판례/실무), C (학술)"
- 유저 응답 후 처리 계속

### Step 4: Frontmatter 생성

변환된 .md 파일에 YAML frontmatter를 자동 생성한다.

```yaml
---
# === 식별 정보 ===
source_id: "{grade}-{category}-{slug}"    # 예: "b-law-firm-kimchang-transfer-2026"
slug: "{자동 생성}"
title_kr: "{문서에서 추출한 제목}"
title_en: "{영문 제목 있으면 추출, 없으면 빈값}"
document_type: "{statute | enforcement_decree | guideline | decision | precedent | newsletter | article | paper}"

# === 소스 정보 ===
source_grade: "{A | B | C}"
publisher: "{발행 기관/로펌/저널명}"
author: "{저자명 (추출 가능한 경우)}"
published_date: "{발행일 (추출 가능한 경우)}"
source_url: "{URL (추출 가능한 경우)}"
original_format: "{pdf | docx | ...}"
ingested_at: "{처리 시각 ISO 8601}"

# === 검색 메타 ===
keywords: ["{내용 기반 키워드 5-10개}"]
topics: ["{주제 분류}"]
jurisdiction: "{KR | US | EU | JP | ...}"
legal_provisions: ["{인용된 법 조문 번호 목록}"]
char_count: {글자수}

# === 검증 ===
verification_status: "{VERIFIED | UNVERIFIED}"
grade_confidence: "{high | medium | low}"
---
```

**핵심 필드 추출 로직:**
1. **제목**: 첫 번째 `#` 헤딩 또는 문서 최상단 볼드 텍스트
2. **키워드**: 법률 도메인 핵심 용어 추출
3. **legal_provisions**: 정규식으로 "제XX조", "Article XX", "Section XX" 패턴 추출
4. **jurisdiction**: 법령/판례의 관할권 판별 (KR/US/EU 등)
5. **publisher**: 기관명, 로펌명, 저널명 등 추출
6. **published_date**: 날짜 패턴 추출 (YYYY.MM.DD, YYYY년 M월 D일, Month DD, YYYY 등)

### Step 5: 목적 폴더로 이동

Grade와 document_type에 따라 자동 배치:

```
Grade A:
  statute, enforcement_decree  → library/grade-a/statutes/
  guideline                    → library/grade-a/guidelines/
  기타 공식 문서                → library/grade-a/{category}/  (필요시 폴더 생성)

Grade B:
  decision                     → library/grade-b/decisions/
  precedent                    → library/grade-b/precedents/
  newsletter, article          → library/grade-b/commentary/
  기타                         → library/grade-b/{category}/

Grade C:
  paper, article               → library/grade-c/academic/
  기타                         → library/grade-c/{category}/
```

**파일명 규칙:** `{slug}.md`
- slug는 제목에서 생성: 한글 유지, 공백→하이픈, 특수문자 제거
- 중복 시 `-2`, `-3` 접미사

**원본 파일:** `library/inbox/_processed/`로 이동 (삭제하지 않음)

### Step 6: 처리 결과 리포트

모든 파일 처리 후 요약 리포트를 출력한다:

```
Ingest 완료

처리: 5개 파일
  Grade A: 1건 (개인정보보호법-시행령-일부개정령안.pdf → grade-a/statutes/)
  Grade B: 2건
     - 김장-제3자제공-뉴스레터.pdf → grade-b/commentary/
     - 대법원-2025다12345.docx → grade-b/precedents/
  Grade C: 1건 (정보법학-가명처리-논문.pdf → grade-c/academic/)
  Grade D (거부): 1건 (뉴스기사.pdf)

원본: library/inbox/_processed/ 로 이동
```

---

## 에러 처리

| 상황 | 대응 |
|------|------|
| inbox 비어있음 | "inbox가 비어 있습니다" 안내 |
| 미지원 포맷 (.hwp 등) | 해당 파일 스킵 + "PDF/DOCX로 변환 필요" 안내 |
| markitdown 변환 실패 | `_failed/`로 이동 + 실패 사유 안내 |
| Grade 판별 불가 | 유저에게 Grade 선택 질문 |
| Grade D 판별 | ingest 거부 + 사유 안내 |
| 파일명 중복 | slug에 `-2`, `-3` 접미사 |
| frontmatter 추출 실패 | 빈 값으로 생성 + `grade_confidence: low` |
| 대용량 파일 (50MB 초과) | 경고 후 유저 확인 요청 |

---

## 주의사항

1. **원본 보존**: inbox 원본은 절대 삭제하지 않음 → `_processed/`로 이동
2. **Grade D 배제**: 뉴스, AI 요약, 위키 등은 ingest 거부
3. **스캔 PDF**: OCR 품질이 낮으면 `grade_confidence: low` + 유저 검토 권고
4. **기존 파일 보호**: 이미 `library/grade-x/`에 있는 동일 slug 파일은 덮어쓰지 않음
5. **검토 용도**: 이 라이브러리의 소스들은 리뷰 시 인용 검증(Dim 1)의 참조 자료로 활용됨
