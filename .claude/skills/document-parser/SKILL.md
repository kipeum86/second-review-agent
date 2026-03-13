# document-parser Skill

Parse DOCX files to extract structure, citations, and defined terms for review pipeline.

## Capabilities

1. **Structure Extraction** (`scripts/parse-docx-structure.py`)
   - Unzips DOCX, parses `word/document.xml` via ElementTree
   - Extracts heading hierarchy (Heading1-6 + Korean patterns: 제X조, 제X항)
   - Builds section map, numbering sequences, cross-reference inventory
   - Outputs full text with paragraph-level metadata
   - Usage: `python3 parse-docx-structure.py <docx_path> <output_dir>`
   - Outputs: `parsed-structure.json` (sections, headings, paragraphs, cross-references, full text)

2. **Citation Extraction** (`scripts/extract-citations.py`)
   - Regex-based extraction for KR/EN/EU citation patterns
   - Korean: 법률 제NNNNN호, 시행령, 대법원 20XX다NNNNN, 제N조제N항제N호
   - US: Title/Section USC, F.2d/3d/4th, CFR
   - EU: Regulation/Directive numbering
   - Usage: `python3 extract-citations.py <parsed_structure_json> <output_path>`
   - Outputs: `citation-list.json` (per citation: text, type, location, claimed_content)

3. **Defined-Term Extraction** (`scripts/extract-defined-terms.py`)
   - Detects definition patterns: "이하 'X'라 한다", "hereinafter referred to as"
   - Builds inventory with definition location and all usage locations
   - Usage: `python3 extract-defined-terms.py <parsed_structure_json> <output_path>`
   - Outputs: `defined-terms.json` (per term: text, definition_location, usage_locations)

## Workflow

```
DOCX file
    │
    ├── parse-docx-structure.py  →  parsed-structure.json
    │
    ├── extract-citations.py     →  citation-list.json
    │
    └── extract-defined-terms.py →  defined-terms.json
```

## When to Use

- WF1 Step 2: Document Parsing & Structure Analysis
- Input: DOCX file path from Step 1 intake
- Must complete before Step 3 (citation verification) and Step 4 (substantive review)

## Failure Handling

- DOCX unpack failure → attempt pandoc fallback: `pandoc input.docx -t markdown -o clean.md`
- If both fail → halt with diagnostic, report to user
- Empty section/citation list is valid (not a failure) — log and proceed

## Checkpoint

After all 3 scripts complete successfully, the main agent updates `checkpoint.json`:
- `step_2.status` → `"completed"`
- `step_2.output` → comma-separated paths of `parsed-structure.json`, `citation-list.json`, `defined-terms.json`
- `last_completed_step` → `2`
