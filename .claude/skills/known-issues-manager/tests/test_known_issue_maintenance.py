import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from known_issue_index import default_index_path, load_index_if_current  # type: ignore  # noqa: E402
from known_issue_ledger import (  # type: ignore  # noqa: E402
    append_occurrence_events,
    build_occurrence_events_from_issue_registry,
)
from known_issue_maintenance import (  # type: ignore  # noqa: E402
    FREQUENCY_CACHE_NAME,
    build_frequency_cache,
    find_registry_files,
    rebuild_known_issue_artifacts,
)


def load_fixture(name: str):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class KnownIssueMaintenanceTests(unittest.TestCase):
    def test_find_registry_files_excludes_generated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = os.path.join(tmp, "legal-writing-agent.json")
            index_path = os.path.join(tmp, "legal-writing-agent.index.json")
            cache_path = os.path.join(tmp, FREQUENCY_CACHE_NAME)
            for path in (registry_path, index_path, cache_path):
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump([], handle)

            self.assertEqual(find_registry_files(tmp), [registry_path])

    def test_rebuild_writes_current_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = os.path.join(tmp, "legal-writing-agent.json")
            shutil.copyfile(os.path.join(FIXTURES, "multi-pattern-registry.json"), registry_path)

            before = rebuild_known_issue_artifacts(tmp, write_indexes=False)
            self.assertEqual(before["registries"][0]["index_status"], "missing")

            report = rebuild_known_issue_artifacts(tmp)
            index_path = default_index_path(registry_path)

            self.assertTrue(os.path.exists(index_path))
            self.assertIsNotNone(load_index_if_current(registry_path))
            self.assertTrue(report["registries"][0]["index_rebuilt"])
            self.assertEqual(report["registries"][0]["index_status"], "current")

    def test_frequency_cache_uses_counts_without_matter_ids(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            cache = build_frequency_cache(ledger_path, agent="legal-writing-agent")

            identity = "signature:legal-writing-agent|d4|advisory|passive_by_overuse"
            self.assertEqual(cache["events_total"], 4)
            self.assertEqual(cache["frequencies"][identity]["frequency"], 3)
            self.assertNotIn("matter_ids", cache["frequencies"][identity])

    def test_rebuild_can_write_frequency_cache(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = os.path.join(tmp, "legal-writing-agent.json")
            shutil.copyfile(os.path.join(FIXTURES, "multi-pattern-registry.json"), registry_path)
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            report = rebuild_known_issue_artifacts(
                tmp,
                ledger_path=ledger_path,
                write_frequency_cache=True,
                agent="legal-writing-agent",
            )
            cache_path = os.path.join(tmp, FREQUENCY_CACHE_NAME)

            self.assertTrue(os.path.exists(cache_path))
            self.assertEqual(report["frequency_cache"]["identity_count"], 1)
            self.assertEqual(report["frequency_cache"]["events_total"], 4)


if __name__ == "__main__":
    unittest.main()
