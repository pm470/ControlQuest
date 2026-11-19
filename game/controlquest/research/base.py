"""What the Research debrief of a level shows (static, offline; AGENTS.md section 8, 2026-11-19).

One `ResearchInfo` per level, in its own file in this package (named after the level id).
The run's numbers are not stored here: the debrief takes them from the level's latest
RunResult. Texts may contain $...$ (shown in the LaTeX font by ui/math_text.py).

Paper summaries are paraphrases of the papers' abstracts. Do not add numbers or claims
from a paper that were not checked in the paper itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperRef:
    key: str  # the key in docs/SCIENTIFIC_UPGRADE_BRIEF.md, e.g. "2A"
    title: str  # as published
    authors: str  # all authors, as published
    year: int
    venue: str  # journal / proceedings with volume(issue) and pages
    url: str  # the link a player can open (the DOI, or the proceedings page)
    problem: str  # the problem the paper addresses
    approach: str  # what the paper does about it
    connection: str  # how it relates to this level
    doi: str = ""  # without "https://doi.org/"
    free_url: str = ""  # an open full text (arXiv), if there is one
    # what was verified, against which source (for docs/RESEARCH.md)
    checked: str = ""


@dataclass(frozen=True)
class ResearchInfo:
    level_id: str
    question: str  # the research question: the debrief's headline
    takeaway: str  # one sentence: the lesson
    problem: str  # "The problem": the scientific problem behind the level
    relevance: str  # "Why it matters": where it shows up in practice
    shown: str  # "What this level showed": how the level demonstrates it (static part)
    limits: str  # "Limits of this level": what the game simplifies (1-2 sentences)
    papers: tuple[PaperRef, ...]  # two recent papers (2022-2025)
