"""Pure functions for profile boundary checks (PRD 4.3).

Two concerns live here, both kept as side-effect-free functions so they
can be unit-tested in isolation:

* **Time-overlap detection** — given the education/experiences items in a
  profile, find pairs whose date ranges overlap by more than 50 % of the
  shorter range.  Date parsing is intentionally conservative: anything that
  is not a plain year, ``YYYY-MM``, ``YYYY-MM-DD``, or an open-ended token
  (``至今``) is treated as *unknown* and never triggers a warning.

* **Draft-reference counting** — given a list of resume-draft dicts (already
  deserialized from JSON) and a ``profile_field_id``, count how many drafts
  reference that id in any of their ``sections``, ``evidence``, or ``gaps``
  payloads.  The id must match exactly — the same string the editor emitted
  and that ``resume.flatten_profile_facts`` wrote into the draft.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

#: Overlap is flagged when the intersection covers at least this fraction of
#: the shorter of the two intervals.
OVERLAP_THRESHOLD = 0.5

_DATE_FULL = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DATE_YM = re.compile(r"^(\d{4})-(\d{1,2})$")
_DATE_Y = re.compile(r"^(\d{4})$")

_OPEN_ENDED = frozenset({"至今", "now", "present", "current"})


def parse_profile_date(raw: Any) -> tuple[date | None, bool]:
    """Conservatively parse a date string from a profile ``start``/``end`` field.

    Returns ``(parsed_date, is_open_ended)``:

    * ``parsed_date`` — a ``date`` for the *start* of the represented period,
      or ``None`` when the string cannot be reliably interpreted.
    * ``is_open_ended`` — ``True`` when the string means "up to now"; the
      caller should treat the end of the interval as *today*.

    Recognised formats (after ``strip``):

    * ``YYYY``      → January 1st of that year
    * ``YYYY-MM``   → the 1st of that month
    * ``YYYY-MM-DD``→ that exact date
    * ``至今`` / ``now`` / ``present`` / ``current`` → open-ended end

    Anything else (partial ranges, Chinese date text, ``2024年3月``, etc.)
    returns ``(None, False)`` — the caller treats the date as unknown and
    skips overlap detection for that item.  We never raise or fabricate a
    date.
    """
    if not isinstance(raw, str):
        return (None, False)
    text = raw.strip()
    if not text:
        return (None, False)
    if text.lower() in _OPEN_ENDED:
        return (date.today(), True)
    for pattern in (_DATE_FULL, _DATE_YM, _DATE_Y):
        m = pattern.match(text)
        if m:
            groups = [int(g) for g in m.groups()]
            year, month, day = groups[0], 1, 1
            if pattern is _DATE_YM:
                month = groups[1]
            elif pattern is _DATE_FULL:
                month, day = groups[1], groups[2]
            try:
                return (date(year, month, day), False)
            except ValueError:
                return (None, False)
    return (None, False)


def _build_interval(start_raw: Any, end_raw: Any) -> tuple[date | None, date | None]:
    """Return ``(start, end)`` date objects from raw start/end strings.

    * If ``start`` cannot be parsed, returns ``(None, None)`` — the item is
      treated as uncheckable.
    * If ``end`` is open-ended (``至今``), ``end`` becomes *today*.
    * If ``end`` is missing but not open-ended, the item is a point interval
      (``end == start``).
    """
    start, _ = parse_profile_date(start_raw)
    if start is None:
        return (None, None)
    end, is_open = parse_profile_date(end_raw)
    if end is None and not is_open:
        end = start
    return (start, end)


def _overlap_ratio(
    a_start: date, a_end: date,
    b_start: date, b_end: date,
) -> float | None:
    """Compute ``intersection / shorter_interval``.

    Returns ``None`` only when both intervals are zero-length points at the
    *same* date — the ratio is undefined in that degenerate case.
    """
    a_end = max(a_end, a_start)
    b_end = max(b_end, b_start)

    a_len = (a_end - a_start).days
    b_len = (b_end - b_start).days
    shorter = min(a_len, b_len)

    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_end < overlap_start:
        return 0.0
    intersection = (overlap_end - overlap_start).days

    if shorter == 0:
        return 1.0 if intersection == 0 and a_start == b_start else 0.0
    return intersection / shorter


def detect_time_overlap(
    items: list[dict[str, Any]],
    new_item: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return existing ``items`` whose range overlaps ``new_item`` by ≥ 50 %.

    * ``new_item`` is excluded from the result by id when its ``id`` matches.
    * Items with unparseable start dates are skipped silently.
    """
    new_start, new_end = _build_interval(new_item.get("start"), new_item.get("end"))
    if new_start is None:
        return []

    new_id = new_item.get("id")
    result: list[dict[str, Any]] = []
    for item in items:
        if new_id is not None and item.get("id") == new_id:
            continue
        item_start, item_end = _build_interval(item.get("start"), item.get("end"))
        if item_start is None:
            continue
        ratio = _overlap_ratio(new_start, new_end, item_start, item_end)
        if ratio is not None and ratio >= OVERLAP_THRESHOLD:
            result.append(item)
    return result


def check_profile_overlaps(
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """Check education and experiences for >50 % time-overlapping pairs.

    Returns ``{"overlap": bool, "items": [...]}`` where ``items`` lists every
    item that participates in at least one overlapping pair (deduplicated by
    id).  The list is empty when ``overlap`` is ``False``.
    """
    flagged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for collection in ("education", "experiences"):
        items = profile_data.get(collection)
        if not isinstance(items, list) or len(items) < 2:
            continue
        for i, a in enumerate(items):
            a_start, a_end = _build_interval(a.get("start"), a.get("end"))
            if a_start is None:
                continue
            for j in range(i + 1, len(items)):
                b = items[j]
                b_start, b_end = _build_interval(b.get("start"), b.get("end"))
                if b_start is None:
                    continue
                ratio = _overlap_ratio(a_start, a_end, b_start, b_end)
                if ratio is not None and ratio >= OVERLAP_THRESHOLD:
                    for item in (a, b):
                        item_id = str(item.get("id", ""))
                        if item_id and item_id not in seen_ids:
                            seen_ids.add(item_id)
                            flagged.append(item)

    return {"overlap": bool(flagged), "items": flagged}


def count_field_references(
    drafts: list[dict[str, Any]],
    field_id: str,
) -> dict[str, Any]:
    """Count how many drafts reference ``field_id`` in sections/evidence/gaps.

    Searches every item in ``sections[].items[]``, every entry in
    ``evidence[]``, and every entry in ``gaps[]`` for a ``profile_field_id``
    that exactly equals ``field_id``.

    Returns ``{"field_id": str, "count": int, "draft_ids": [int, ...]}``.
    """
    draft_ids: list[int] = []
    for draft in drafts:
        if _draft_references_field(draft, field_id):
            draft_ids.append(int(draft["id"]))
    return {"field_id": field_id, "count": len(draft_ids), "draft_ids": draft_ids}


def _draft_references_field(draft: dict[str, Any], field_id: str) -> bool:
    """True when *any* section/evidence/gap item in ``draft`` references ``field_id``."""
    for section in draft.get("sections") or []:
        for item in section.get("items") or []:
            if item.get("profile_field_id") == field_id:
                return True
    for ev in draft.get("evidence") or []:
        if ev.get("profile_field_id") == field_id:
            return True
    for gap in draft.get("gaps") or []:
        if gap.get("profile_field_id") == field_id:
            return True
    return False
