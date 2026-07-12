from src.graph.nodes.summarize import _compose_report


def test_report_status_and_counts_are_deterministic() -> None:
    report = _compose_report(
        [
            {
                "url": "https://example.com",
                "results": [
                    {"test_name": "loads", "status": "pass", "evidence": "ok"},
                    {"test_name": "checkout", "status": "error", "evidence": "provider"},
                ],
            }
        ],
        "Model narrative",
    )

    assert "**Status:** ERROR" in report
    assert "**Total:** 2" in report
    assert "**Passed:** 1" in report
    assert "**Errors:** 1" in report
    assert "## LLM Narrative" in report
