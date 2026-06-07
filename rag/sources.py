"""Registry of project sources with per-source fetch + chunking parameters.

Chunk size/overlap follow CLAUDE.md's per-source Chunking Strategy table
(authoritative). `mode`: "atomic" = 1 unit (review/comment) -> 1 chunk, no overlap;
"prose" = recursive semantic split with overlap.
"""
from dataclasses import dataclass, field
from typing import Optional

VALID_SOURCE_TYPES = {"official", "editorial", "user_opinion"}


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    title: str
    source_type: str          # official | editorial | user_opinion
    fetch: str                # live | snapshot | export
    mode: str                 # prose | atomic
    size_min: int
    size_max: int
    overlap: int = 0
    author: Optional[str] = None
    date: Optional[str] = None
    commercial_bias: bool = False
    weebly_subpages: tuple = field(default=())


SOURCE_REGISTRY = [
    Source("ratemyprofessors",
           "https://www.ratemyprofessors.com/search/professors/15723?q=*&did=11",
           "RateMyProfessors — ASU", "user_opinion", "export", "atomic", 50, 200),
    Source("quora",
           "https://www.quora.com/Which-professors-at-Arizona-State-University-would-you-recommend-that-people-take-classes-from-and-why",
           "Quora — ASU professor recommendations", "user_opinion", "export", "atomic", 100, 600),
    Source("myprofreviews",
           "https://www.myprofreviews.com/r/2467-arizona-state-university-professor",
           "MyProfReviews — ASU", "editorial", "live", "atomic", 100, 200),
    Source("rambler_tempe",
           "https://ramblertempe.com/resources/a-freshmans-guide-to-student-housing-at-arizona-state-university/",
           "Rambler Tempe — Freshman Housing Guide", "editorial", "snapshot", "prose",
           300, 500, overlap=60, commercial_bias=True),
    Source("asuonline_finals",
           "https://asuonline.asu.edu/newsroom/online-learning-tips/survive-finals-week/",
           "ASU Online — Survive Finals Week", "official", "live", "prose", 150, 400, overlap=40),
    Source("heysunny",
           "https://heysunny.asu.edu/blog/finals-advice-you-can-actually-use",
           "Hey Sunny — Finals Advice", "official", "live", "prose", 400, 700, overlap=80),
    Source("asunews_miceli",
           "https://news.asu.edu/20250414-sun-devil-community-tested-tips-taking-exams",
           "ASU News — Tested Tips for Taking Exams", "official", "live", "prose", 300, 600, overlap=60),
    Source("reddit",
           "https://www.reddit.com/r/ASU/comments/seracn/hey_devils_what_are_the_best_tips_youve_ever/",
           "Reddit r/ASU — Best tips thread", "user_opinion", "export", "atomic", 50, 400),
    Source("asuonline_checklist",
           "https://asuonline.asu.edu/newsroom/online-learning-tips/prepare-first-year-college-student-checklist/",
           "ASU Online — First-Year Checklist", "official", "live", "prose", 200, 400, overlap=40),
    Source("weebly",
           "https://asusurvivalguide.weebly.com/",
           "ASU Survival Guide (Weebly)", "editorial", "live", "prose", 200, 500, overlap=50,
           weebly_subpages=("food-and-fun", "housing", "resources", "getting-around")),
    Source("plexuss",
           "https://plexuss.com/n/arizona-state-university-survival-guide",
           "Plexuss — ASU Survival Guide", "editorial", "live", "prose", 200, 500, overlap=50),
]
