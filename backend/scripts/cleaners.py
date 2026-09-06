"""Text cleaning and boilerplate removal for CourseCompass document chunks."""
import re

# Repeated disclaimer that appears at the bottom of every IP page.
IP_BOILERPLATE_PHRASES = (
    "an instruction plan is only a tentative plan",
    "the teacher may make some changes in his/her teaching plan",
    "updated on the contemporary issues related to the course",
    "the students are advised to use syllabus for preparation of all examinations",
)

# Footer / page furniture patterns.
FOOTER_PATTERNS = (
    re.compile(r"\bSession\s+\d{4}\s*-\s*\d{2}\b", re.IGNORECASE),
    re.compile(r"\bPage\s*:\s*\d+\s*/\s*\d+\b"),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
)

WS_RE = re.compile(r"[ \t]+")
LINE_WS_RE = re.compile(r"\s+")


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace inside lines and strip empty inter-line space."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def normalize_whitespace(text: str) -> str:
    """Collapse ALL whitespace (including newlines) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def strip_footer(text: str) -> str:
    """Remove session/page-number footer lines."""
    out = []
    for line in text.splitlines():
        if any(p.search(line) for p in FOOTER_PATTERNS):
            continue
        out.append(line)
    return "\n".join(out)


def is_boilerplate(text: str) -> bool:
    """True if text is repeated boilerplate / junk, not useful for retrieval."""
    lowered = normalize_whitespace(text).lower()
    if not lowered:
        return True
    if lower_matches_phrase(lowered, IP_BOILERPLATE_PHRASES, min_chars=24):
        return True
    if _looks_like_page_furniture(text):
        return True
    return False


def lower_matches_phrase(lowered: str, phrases, min_chars: int = 0) -> bool:
    for phrase in phrases:
        if phrase in lowered:
            return True
    return False


def _looks_like_page_furniture(text: str) -> bool:
    stripped = normalize_whitespace(text)
    lowered = stripped.lower()
    if any(p.search(text) for p in FOOTER_PATTERNS):
        return True
    if len(stripped) < 4:
        return True
    if stripped.isdigit():
        return True
    if re.fullmatch(r"\d+", stripped):
        return True
    return False


def clean_chunk_text(text: str) -> str:
    """Normalize + strip footers for a chunk's content."""
    text = strip_footer(text)
    
    # Remove the large instruction plan boilerplate to prevent entire blocks from being dropped
    text = re.sub(
        r"An instruction plan is only a tentative plan.*?mentioned in the instruction plan\.?",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    return collapse_whitespace(text).strip()