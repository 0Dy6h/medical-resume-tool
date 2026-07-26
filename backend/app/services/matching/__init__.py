"""Requirement segmentation and profile↔requirement matching.

Split out from ``services.resume`` so the two concerns are separable and
independently testable:

- :mod:`segment` turns a raw Chinese job announcement into the clauses that are
  actually requirements, discarding application procedure and employer
  self-description.
- :mod:`tokenize` provides the CJK token space (character bigrams) the scorer
  compares in, since Chinese has no whitespace word boundaries.

``services.classifier.extract_requirements`` is deliberately untouched: it feeds
the persisted ``jobs.requirements`` column and the ``/api/jobs`` filters, so
changing it rewrites stored data and needs its own migration.
"""

from app.services.matching.segment import (
    REQUIREMENT_HEADINGS,
    SegmentedRequirements,
    segment_requirements,
)
from app.services.matching.tokenize import bigrams, tokenize

__all__ = [
    "REQUIREMENT_HEADINGS",
    "SegmentedRequirements",
    "segment_requirements",
    "bigrams",
    "tokenize",
]
