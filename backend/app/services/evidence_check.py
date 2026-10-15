"""ExtractionEvidenceChecker — verifies the document extractor agent's citations.

The agent is asked for a verbatim excerpt and a page number for every field.
Asking isn't enough: a fabricated but well-formed citation would pass schema
validation. So before an extraction is stored, every citation is checked
against the PDF's own text layer:

1. The excerpt must appear in the document. Matching ignores case, spacing,
   punctuation and line-break hyphens, because PDF text layers reflow
   freely; it does not ignore any letters or digits. An excerpt the model
   shortened with "..." matches when each piece appears, in order, on one page.
2. The cited page must be the page it's on. A citation to the wrong page
   (or a page that doesn't exist) is corrected when the excerpt is found
   elsewhere.
3. For amounts, dates and policy numbers, the excerpt must also support the
   value: `sum_insured = 2500000` needs "25,00,000", "25 lakh" or similar in
   the excerpt, not just any real sentence from the policy.

A field that fails stays visible to the broker but is marked unverified, its
confidence is capped, and the analysis agent is told to treat it as unknown.
Exclusions and riders are paraphrased by design, so they are checked by word
overlap with the cited page instead of verbatim.
"""
from __future__ import annotations

import contextlib
import re
import unicodedata
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation

from app.schemas.extraction import (
    DocumentExtractionLLMSchema,
    ExclusionItem,
    FieldEvidence,
    RiderItem,
)

SCALAR_FIELDS: tuple[str, ...] = (
    "policy_type",
    "provider",
    "policy_number",
    "insured_name",
    "sum_insured",
    "premium_amount",
    "premium_frequency",
    "renewal_date",
)

_MONTHS = {
    m: i
    for i, names in enumerate(
        (
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for m in names
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ELLIPSIS_RE = re.compile(r"\.{3,}|…")
_AMOUNT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|lac\b|l\b)?", re.IGNORECASE
)
_STOPWORDS = frozenset({
    "this", "that", "with", "from", "under", "shall", "will", "such", "than", "have",
    "been", "other", "which", "their", "there", "policy", "insured", "cover",
    "covered", "coverage", "benefit", "benefits", "including",
})


class ExtractionEvidenceChecker:
    """Checks one extraction against the page texts the agent was given."""

    UNVERIFIED_CONFIDENCE_CAP = 0.3
    # Paraphrased list items: share of their significant words found on a page.
    LIST_ITEM_WORD_COVERAGE = 0.7
    # An excerpt with one garbled character still counts if this much of it
    # matches contiguously.
    FUZZY_MATCH_RATIO = 0.9
    _MIN_EXCERPT_CHARS = 4

    def __init__(self, pages: list[str]) -> None:
        """`pages[i]` is the text of page i + 1 ("" for a page with no text)."""
        self._pages = [self.compact(p) for p in pages]
        self._page_words = [set(self.words(p)) for p in pages]
        self._value_checks: dict[str, Callable[[str, str], bool]] = {
            "sum_insured": self._amount_supported,
            "premium_amount": self._amount_supported,
            "renewal_date": self._date_supported,
            "policy_number": self._identifier_supported,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check(self, parsed: DocumentExtractionLLMSchema) -> DocumentExtractionLLMSchema:
        """Return a copy of `parsed` with every citation verified or flagged."""
        evidence = {k: v.model_copy() for k, v in parsed.evidence.items()}
        for field in SCALAR_FIELDS:
            value = getattr(parsed, field)
            ev = evidence.get(field)
            if value is None:
                if ev is not None:
                    ev.verified = None
                    ev.verification_note = None
                continue
            if ev is None:
                ev = FieldEvidence(confidence=0.0)
                evidence[field] = ev
            self._check_field(field, str(value), ev)

        return parsed.model_copy(
            update={
                "evidence": evidence,
                "exclusions": [self._check_list_item(e, e.text) for e in parsed.exclusions],
                "riders": [self._check_list_item(r, r.name) for r in parsed.riders],
            }
        )

    @staticmethod
    def summary(parsed: DocumentExtractionLLMSchema) -> tuple[int, int]:
        """(verified, unverified) counts across scalar fields — for logging."""
        flags = [ev.verified for ev in parsed.evidence.values() if ev.verified is not None]
        return sum(flags), len(flags) - sum(flags)

    # ------------------------------------------------------------------
    # Scalar fields
    # ------------------------------------------------------------------
    def _check_field(self, field: str, value: str, ev: FieldEvidence) -> None:
        excerpt = ev.source_excerpt or ""
        if len(self.compact(excerpt)) < self._MIN_EXCERPT_CHARS:
            self._flag(ev, "No excerpt was cited for this value.")
            return

        found_on = self._find_excerpt(excerpt, ev.source_page)
        if found_on is None:
            self._flag(ev, "The cited excerpt was not found in the document.")
            return

        value_check = self._value_checks.get(field)
        if value_check is not None and not value_check(value, excerpt):
            self._flag(ev, "The cited excerpt does not contain this value.")
            return

        ev.verified = True
        if ev.source_page != found_on:
            cited = f"page {ev.source_page}" if ev.source_page else "no page"
            ev.verification_note = f"Cited {cited}; found on page {found_on}."
            ev.source_page = found_on
        else:
            ev.verification_note = None

    def _flag(self, ev: FieldEvidence, note: str) -> None:
        ev.verified = False
        ev.verification_note = note
        ev.confidence = min(ev.confidence, self.UNVERIFIED_CONFIDENCE_CAP)

    def _find_excerpt(self, excerpt: str, cited_page: int | None) -> int | None:
        """1-indexed page holding the excerpt, preferring the cited page."""
        pieces = [
            self.compact(p)
            for p in _ELLIPSIS_RE.split(excerpt)
            if len(self.compact(p)) >= self._MIN_EXCERPT_CHARS
        ]
        if not pieces:
            return None
        for page_no in self._search_order(cited_page):
            if self._page_contains(self._pages[page_no - 1], pieces):
                return page_no
        return None

    def _page_contains(self, page: str, pieces: list[str]) -> bool:
        pos = 0
        for piece in pieces:
            at = page.find(piece, pos)
            if at < 0:
                return len(pieces) == 1 and self._fuzzy_contains(page, piece)
            pos = at + len(piece)
        return True

    def _fuzzy_contains(self, page: str, piece: str) -> bool:
        """Tolerate a stray character: a long enough prefix or suffix matches."""
        need = int(len(piece) * self.FUZZY_MATCH_RATIO)
        if need < 12:  # short excerpts must match exactly
            return False
        return piece[:need] in page or piece[-need:] in page

    def _search_order(self, cited_page: int | None) -> list[int]:
        pages = range(1, len(self._pages) + 1)
        if cited_page is not None and 1 <= cited_page <= len(self._pages):
            return [cited_page, *(p for p in pages if p != cited_page)]
        return list(pages)

    # ------------------------------------------------------------------
    # Value-in-excerpt checks
    # ------------------------------------------------------------------
    def _amount_supported(self, value: str, excerpt: str) -> bool:
        target = self.to_decimal(value)
        if target is None:
            return False
        return any(abs(amount - target) < 1 for amount in self.amounts_in(excerpt))

    def _date_supported(self, value: str, excerpt: str) -> bool:
        try:
            target = date.fromisoformat(value.strip()[:10])
        except ValueError:
            return False
        return target in self.dates_in(excerpt)

    def _identifier_supported(self, value: str, excerpt: str) -> bool:
        compact_value = self.compact(value)
        return bool(compact_value) and compact_value in self.compact(excerpt)

    # ------------------------------------------------------------------
    # Exclusions / riders
    # ------------------------------------------------------------------
    def _check_list_item(
        self, item: ExclusionItem | RiderItem, text: str
    ) -> ExclusionItem | RiderItem:
        words = [w for w in self.words(text) if len(w) >= 4 and w not in _STOPWORDS]
        if not words:
            return item.model_copy(update={"verified": False})
        for page_no in self._search_order(item.source_page):
            page_words = self._page_words[page_no - 1]
            coverage = sum(w in page_words for w in words) / len(words)
            if coverage >= self.LIST_ITEM_WORD_COVERAGE:
                return item.model_copy(update={"verified": True, "source_page": page_no})
        return item.model_copy(update={"verified": False})

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------
    @staticmethod
    def compact(text: str) -> str:
        """Letters and digits only, lower-cased: immune to PDF reflow."""
        text = unicodedata.normalize("NFKC", text).lower().replace("₹", "rs")
        return re.sub(r"[^a-z0-9]", "", text)

    @staticmethod
    def words(text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text).lower()
        return re.findall(r"[a-z0-9]+", re.sub(r"-\s*\n\s*", "", text))

    @staticmethod
    def to_decimal(value: str) -> Decimal | None:
        try:
            return Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def amounts_in(cls, text: str) -> list[Decimal]:
        """Every amount in `text`, with lakh/crore units applied."""
        amounts: list[Decimal] = []
        for number, unit in _AMOUNT_RE.findall(text):
            base = cls.to_decimal(number)
            if base is None:
                continue
            unit = unit.lower()
            if unit.startswith("cr"):
                base *= 10_000_000
            elif unit.startswith(("lakh", "lac")) or unit == "l":
                base *= 100_000
            amounts.append(base)
        return amounts

    @staticmethod
    def dates_in(text: str) -> set[date]:
        """Dates in the formats Indian policies use (day-first when numeric)."""
        text = text.lower()
        found: set[date] = set()

        def add(y: str, m: int, d: str) -> None:
            year = int(y) + (2000 if len(y) == 2 else 0)
            with contextlib.suppress(ValueError):  # e.g. 31 Feb
                found.add(date(year, m, int(d)))

        for y, m, d in re.findall(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text):
            add(y, int(m), d)
        for d, m, y in re.findall(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})\b", text):
            add(y, int(m), d)
        for d, mon, y in re.findall(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s\-/.,]*({_MONTH_RE})[a-z]*[\s\-/.,']*(\d{{4}}|\d{{2}})\b", text
        ):
            add(y, _MONTHS[mon], d)
        for mon, d, y in re.findall(
            rf"\b({_MONTH_RE})[a-z]*[\s\-/.]*(\d{{1,2}})(?:st|nd|rd|th)?[\s,\-/.]+(\d{{4}})\b", text
        ):
            add(y, _MONTHS[mon], d)
        return found


__all__ = ["SCALAR_FIELDS", "ExtractionEvidenceChecker"]
