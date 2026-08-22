"""Unit tests for _review_status aligned with PRD 4.6 health-degradation rules."""

from app.services.analytics import _review_status


def _stats(
    *,
    jobs: int = 10,
    low_confidence_jobs: int = 0,
    failed_attachment_events: int = 0,
) -> dict:
    return {
        "jobs": jobs,
        "low_confidence_jobs": low_confidence_jobs,
        "attachment_sourced_jobs": 0,
        "failed_attachment_events": failed_attachment_events,
        "confidence_sum": 0.0,
    }


def test_review_status_stable():
    stats = _stats(jobs=10, low_confidence_jobs=0, failed_attachment_events=0)
    assert _review_status(stats, average_confidence=0.9, low_confidence_ratio=0.0) == "stable"


def test_review_status_watch_low_avg():
    stats = _stats(jobs=10, low_confidence_jobs=0, failed_attachment_events=0)
    assert _review_status(stats, average_confidence=0.65, low_confidence_ratio=0.0) == "watch"


def test_review_status_watch_high_ratio():
    stats = _stats(jobs=10, low_confidence_jobs=3, failed_attachment_events=0)
    assert _review_status(stats, average_confidence=0.85, low_confidence_ratio=0.25) == "watch"


def test_review_status_review_on_failure():
    stats = _stats(jobs=10, low_confidence_jobs=0, failed_attachment_events=1)
    assert _review_status(stats, average_confidence=0.95, low_confidence_ratio=0.0) == "review"


def test_review_status_low_conf_not_review():
    """Regression: a single low-confidence job among many no longer triggers review."""
    stats = _stats(jobs=20, low_confidence_jobs=1, failed_attachment_events=0)
    assert _review_status(stats, average_confidence=0.9, low_confidence_ratio=0.05) == "stable"
