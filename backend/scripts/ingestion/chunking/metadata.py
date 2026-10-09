"""Typed ``Chunk.metadata`` builders.

One frozen dataclass per ``(doc_type, chunk_type)``; ``to_dict()`` emits
exactly the JSONB keys documented in ``ingestion/README.md``. Nothing in the
app or frontend reads ``chunk_metadata`` yet, so this schema is the single
source of truth for what each chunk type carries.

``document_kind`` and the benefits ``type`` key used to duplicate
``Chunk.doc_type`` / ``Chunk.chunk_type`` and are dropped here.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ChunkMeta:
    """Base for all chunk metadata; ``to_dict()`` serializes the fields."""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Instruction Plan (IP)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IpCourseOverviewMeta(ChunkMeta):  # no fields
    pass


@dataclass(frozen=True)
class IpCourseOutcomeMeta(ChunkMeta):
    co_num: int


@dataclass(frozen=True)
class IpReferenceMeta(ChunkMeta):
    ref_code: str


@dataclass(frozen=True)
class IpLectureMeta(ChunkMeta):
    week: int | None
    lecture: int


@dataclass(frozen=True)
class IpTableRowMeta(ChunkMeta):  # no fields
    pass


# ---------------------------------------------------------------------------
# Syllabus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyllabusCourseOverviewMeta(ChunkMeta):  # no fields
    pass


@dataclass(frozen=True)
class SyllabusReferencesMeta(ChunkMeta):  # no fields
    pass


@dataclass(frozen=True)
class SyllabusCourseOutcomeMeta(ChunkMeta):
    co_num: int


@dataclass(frozen=True)
class SyllabusOutcomeBlobMeta(ChunkMeta):  # no CO markers found; one blob chunk
    pass


@dataclass(frozen=True)
class SyllabusPracticalMeta(ChunkMeta):
    practical_no: int


@dataclass(frozen=True)
class SyllabusUnitMeta(ChunkMeta):
    unit: int
    unit_label: str


# ---------------------------------------------------------------------------
# Benefits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenefitsPolicyOverviewMeta(ChunkMeta):
    section: str
    table_index: int


@dataclass(frozen=True)
class BenefitsCriteriaRowMeta(ChunkMeta):
    section: str
    table_index: int
    fields: dict


@dataclass(frozen=True)
class BenefitsSpecialNoteMeta(ChunkMeta):
    section: str
    table_index: int