# library-manager Skill

Manage review library assets: writing samples, style profiles, checklists, and known-issue patterns.

## Capabilities

1. **Library Status** (`/library list`)
   - Scan all library directories and report counts + status
   - Output: asset summary table (samples, checklists, known-issues, style-profiles)

2. **Sample Ingestion** (`/library add-sample`)
   - Accept DOCX, PDF, or Markdown files
   - Extract text using `document-parser` scripts or plain read
   - Compute style metrics using `ingest-sample.py`
   - Store extracted text + metrics in `library/samples/{filename}.json`
   - After ingestion, report current sample count and whether style profile can be (re)generated

3. **Style Profile Generation** (`/library style-profile regenerate`)
   - Requires ≥5 samples in `library/samples/`
   - Run `build-style-profile.py` to aggregate metrics across all samples
   - Compute: mean + standard deviation for each metric (avg_sentence_length, passive_voice_ratio, formality_score, avg_paragraph_length, citation_density)
   - Output: `library/style-profiles/{profile_name}.json`
   - `/library style-profile view` — display current profile metrics

4. **Checklist Management** (`/library add-checklist`)
   - Validate YAML structure against expected schema (document_type, language, description, dimensions with items)
   - Save to `library/checklists/{document_type}-{language}.yaml`
   - `/library add-checklist` with no file → interactive: ask document type, language, then generate skeleton

5. **Known Issues Management** (`/library known-issues`)
   - `list` — display all patterns grouped by agent, with frequency and last_seen
   - `add` — interactive: collect dimension, pattern, detection_rule, recommended_fix; assign pattern_id
   - `edit {pattern_id}` — modify an existing pattern
   - `delete {pattern_id}` — remove pattern (with confirmation)

## Scripts

### `scripts/ingest-sample.py`
Extract text from a file and compute style metrics for library storage.
- Input: file path (DOCX, PDF, MD, or TXT)
- For DOCX: delegates to `document-parser/scripts/parse-docx-structure.py` then reads full_text
- For others: direct text read
- Computes metrics using same logic as `style-fingerprint-compare.py`
- Output: JSON to stdout with `{filename, source_path, ingested_at, text_length, metrics}`
- Usage: `python3 ingest-sample.py <file_path>`

### `scripts/build-style-profile.py`
Aggregate all sample metrics into a style fingerprint profile.
- Input: samples directory path, output path
- Reads all `*.json` files in samples directory
- Computes mean and standard deviation for each metric
- Output: style profile JSON with `{profile_name, sample_count, created_at, metrics (means), standard_deviations}`
- Usage: `python3 build-style-profile.py <samples_dir> <output_path>`

### `scripts/validate-checklist.py`
Validate a YAML checklist file against the expected schema.
- Input: YAML file path
- Checks: required top-level keys (document_type, language, description, dimensions), dimensions is a dict with list values
- Output: JSON with validation result + any errors
- Usage: `python3 validate-checklist.py <yaml_path>`

## When to Use

- WF4: `/library` command and all sub-commands
- Post-review: when `known-issues-manager` proposes a new pattern
- Onboarding: when setting up library for a new document author/agent

## Checkpoint

Library management operations (WF4) do not use the checkpoint system — they are atomic operations that complete immediately.
