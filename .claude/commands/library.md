Manage the review library: samples, checklists, known issues, and style profiles.

Route to the appropriate sub-command based on $ARGUMENTS:

| Sub-command | Action |
|-------------|--------|
| `add-sample` | Ingest a writing sample from `library/samples/` for style fingerprint generation. Requires DOCX/PDF/MD file. |
| `add-checklist` | Add or update a document-type-specific review checklist in `library/checklists/`. Expects YAML format. |
| `known-issues` | View, add, or edit known issue patterns in `library/known-issues/`. Sub-options: `list`, `add`, `edit {pattern_id}`, `delete {pattern_id}` |
| `style-profile` | View or regenerate the style fingerprint from samples. Sub-options: `view`, `regenerate`. Requires ≥5 samples. |
| `list` | List all library assets (samples, checklists, known-issues, style-profiles) with counts and status. |

If no sub-command specified, show available options and current library status.

Examples:
- `/library list` → show all library contents
- `/library add-sample` → prompt for file path, ingest sample
- `/library known-issues list` → show all known issue patterns
- `/library style-profile regenerate` → re-analyze all samples and rebuild fingerprint
