#!/usr/bin/env bash
# Citation Search Executor — Reference & Test Harness
#
# This script documents the MCP search invocation patterns by jurisdiction.
# Actual MCP tool calls (WebSearch, WebFetch) are executed by the LLM agent directly.
# This file serves as a reference for query construction and as a test harness.
#
# Usage: bash search-executor.sh <jurisdiction> <citation_type> <citation_text>

set -euo pipefail

JURISDICTION="${1:-}"
CITATION_TYPE="${2:-}"
CITATION_TEXT="${3:-}"

if [ -z "$JURISDICTION" ] || [ -z "$CITATION_TYPE" ] || [ -z "$CITATION_TEXT" ]; then
    echo '{"error": "Usage: search-executor.sh <jurisdiction> <citation_type> <citation_text>"}'
    exit 1
fi

# ── Query Construction Templates ──

case "$JURISDICTION" in
    KR)
        case "$CITATION_TYPE" in
            statute)
                echo "Search queries for Korean statute verification:"
                echo "  1. WebSearch: site:law.go.kr \"${CITATION_TEXT}\""
                echo "  2. WebFetch: https://law.go.kr/법령/${CITATION_TEXT}"
                echo "  3. WebSearch: \"${CITATION_TEXT}\" 법률 조문"
                ;;
            case)
                echo "Search queries for Korean case verification:"
                echo "  1. WebSearch: site:glaw.scourt.go.kr ${CITATION_TEXT}"
                echo "  2. WebSearch: 대법원 ${CITATION_TEXT} 판결"
                echo "  3. WebFetch: https://glaw.scourt.go.kr/ (search page)"
                ;;
            regulation)
                echo "Search queries for Korean regulation verification:"
                echo "  1. WebSearch: site:law.go.kr \"${CITATION_TEXT}\" 시행령"
                echo "  2. WebFetch: https://law.go.kr/법령/${CITATION_TEXT}"
                ;;
            *)
                echo "Unsupported citation type: $CITATION_TYPE"
                ;;
        esac
        ;;
    US)
        case "$CITATION_TYPE" in
            statute)
                echo "Search queries for US statute verification:"
                echo "  1. WebSearch: site:congress.gov \"${CITATION_TEXT}\""
                echo "  2. WebFetch: https://uscode.house.gov/view.xhtml?req=${CITATION_TEXT}"
                echo "  3. WebSearch: ${CITATION_TEXT} United States Code"
                ;;
            case)
                echo "Search queries for US case verification:"
                echo "  1. WebSearch: \"${CITATION_TEXT}\" court opinion"
                echo "  2. WebFetch: https://www.courtlistener.com/ (search)"
                echo "  3. WebSearch: site:scholar.google.com \"${CITATION_TEXT}\""
                ;;
            regulation)
                echo "Search queries for US regulation verification:"
                echo "  1. WebSearch: site:ecfr.gov \"${CITATION_TEXT}\""
                echo "  2. WebFetch: https://www.ecfr.gov/current/title-X/section-Y"
                ;;
            *)
                echo "Unsupported citation type: $CITATION_TYPE"
                ;;
        esac
        ;;
    EU)
        case "$CITATION_TYPE" in
            regulation|treaty)
                echo "Search queries for EU regulation verification:"
                echo "  1. WebSearch: site:eur-lex.europa.eu \"${CITATION_TEXT}\""
                echo "  2. WebFetch: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:..."
                echo "  3. WebSearch: \"${CITATION_TEXT}\" EUR-Lex"
                ;;
            *)
                echo "Unsupported citation type: $CITATION_TYPE"
                ;;
        esac
        ;;
    *)
        echo "Unsupported jurisdiction: $JURISDICTION"
        exit 1
        ;;
esac
