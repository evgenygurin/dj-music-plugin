"""Rock-solid track matching against the Beatport catalog.

A title string alone is not trustworthy — search returns remixes, namesakes,
and bootlegs. We only trust a Beatport row as "the same recording" when the
text matches AND an independent audio signal we already computed (BPM and/or
duration) agrees. The result carries an explicit confidence tier so callers
can gate on it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

# Mix/version qualifiers stripped before comparing titles.
_MIX_NOISE = re.compile(
    r"\b(original|extended|radio|club|dub|instrumental|edit|mix|version|remix)\b",
    re.IGNORECASE,
)
_FEAT = re.compile(r"\b(feat|ft|featuring|with)\b.*$", re.IGNORECASE)
_PAREN = re.compile(r"[\(\[].*?[\)\]]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_text(s: str | None) -> str:
    """Lowercase, strip accents / feat. / bracketed mix tags / punctuation."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = _PAREN.sub(" ", s)
    s = _FEAT.sub(" ", s)
    s = _MIX_NOISE.sub(" ", s)
    s = _NON_ALNUM.sub(" ", s)
    return " ".join(s.split())


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    confidence: str  # "high" | "medium" | "low" | "none"
    score: float  # 0..1 text similarity (title+artist)
    beatport_id: int | None
    reasons: tuple[str, ...]
    track: dict[str, Any] | None  # normalized Beatport track (see adapter)


def score_candidate(
    *,
    cand: dict[str, Any],
    title: str,
    artist: str,
    bpm: float | None,
    duration_ms: int | None,
    isrc: str | None,
    bpm_tol: float,
    dur_tol_ms: int,
) -> tuple[float, list[str], bool, bool]:
    """Return (text_score, reasons, bpm_ok, dur_ok) for one candidate.

    ``cand`` is a *normalized* Beatport track dict (adapter.normalize_track).
    """
    reasons: list[str] = []

    # ISRC is definitive when both sides have it.
    cand_isrc = (cand.get("isrc") or "").strip().upper()
    if isrc and cand_isrc and isrc.strip().upper() == cand_isrc:
        reasons.append("isrc-exact")
        return 1.0, reasons, True, True

    t_score = _ratio(normalize_text(title), normalize_text(cand.get("title")))
    cand_artists = " ".join(normalize_text(a) for a in cand.get("artists", []))
    a_score = max(
        (_ratio(normalize_text(artist), normalize_text(a)) for a in cand.get("artists", [])),
        default=0.0,
    )
    # Artist may be a multi-name string on our side — also try substring overlap.
    if artist and cand_artists:
        a_score = max(a_score, _ratio(normalize_text(artist), cand_artists))
    text_score = 0.6 * t_score + 0.4 * a_score
    if t_score >= 0.85:
        reasons.append(f"title~{t_score:.2f}")
    if a_score >= 0.7:
        reasons.append(f"artist~{a_score:.2f}")

    bpm_ok = False
    if bpm is not None and cand.get("bpm"):
        if abs(float(cand["bpm"]) - float(bpm)) <= bpm_tol:
            bpm_ok = True
            reasons.append("bpm-ok")
        # Half/double-time equivalence (audio detectors love octave errors).
        elif (
            min(
                abs(float(cand["bpm"]) - 2 * float(bpm)),
                abs(float(cand["bpm"]) - 0.5 * float(bpm)),
            )
            <= bpm_tol
        ):
            bpm_ok = True
            reasons.append("bpm-octave")

    dur_ok = False
    if (
        duration_ms is not None
        and cand.get("length_ms")
        and abs(int(cand["length_ms"]) - int(duration_ms)) <= dur_tol_ms
    ):
        dur_ok = True
        reasons.append("dur-ok")

    return text_score, reasons, bpm_ok, dur_ok


def pick_best(
    *,
    candidates: list[dict[str, Any]],
    title: str,
    artist: str,
    bpm: float | None = None,
    duration_ms: int | None = None,
    isrc: str | None = None,
    bpm_tol: float = 1.5,
    dur_tol_ms: int = 3000,
) -> MatchResult:
    """Score every candidate and return the best with a confidence tier.

    Confidence tiers:
      * high   — ISRC match, OR strong text (>=0.82) + (bpm OR duration agrees)
      * medium — strong text (>=0.82) but no audio confirmation
      * low    — moderate text (>=0.6) only
      * none   — nothing credible
    """
    best: tuple[float, list[str], bool, bool, dict[str, Any]] | None = None
    for cand in candidates:
        score, reasons, bpm_ok, dur_ok = score_candidate(
            cand=cand,
            title=title,
            artist=artist,
            bpm=bpm,
            duration_ms=duration_ms,
            isrc=isrc,
            bpm_tol=bpm_tol,
            dur_tol_ms=dur_tol_ms,
        )
        # Rank by (audio-confirmed, text score) so a confirmed weaker-text
        # candidate beats an unconfirmed slightly-stronger one.
        if best is None or (bpm_ok or dur_ok, score) > (best[2] or best[3], best[0]):
            best = (score, reasons, bpm_ok, dur_ok, cand)

    if best is None:
        return MatchResult(False, "none", 0.0, None, (), None)

    score, reasons, bpm_ok, dur_ok, cand = best
    isrc_exact = "isrc-exact" in reasons
    if isrc_exact or (score >= 0.82 and (bpm_ok or dur_ok)):
        conf = "high"
    elif score >= 0.82:
        conf = "medium"
    elif score >= 0.6:
        conf = "low"
    else:
        return MatchResult(False, "none", score, cand.get("beatport_id"), tuple(reasons), None)

    return MatchResult(
        matched=conf in ("high", "medium"),
        confidence=conf,
        score=round(score, 3),
        beatport_id=cand.get("beatport_id"),
        reasons=tuple(reasons),
        track=cand,
    )
