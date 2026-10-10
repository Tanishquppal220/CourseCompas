"""Top-level curriculum seed routine.

Entrypoint: ``uv run python scripts/seed.py``.

Loads the full curriculum (Terms 1-8, all term-specific baskets, and the
shared Open Minor basket) into Postgres using the models in app.models.
Safe to re-run.
"""

from app.database import SessionLocal, upgrade_schema
from app.models import (
    BasketOption,
    Course,
    CourseNature,
    CourseType,
    ElectiveBasket,
    Term,
    TermSlot,
)

from .curriculum_data import (
    BASKETS,
    COURSE_NATURES,
    COURSE_TYPES,
    OM_SHARED,
    TERM_PLANS,
)
from .loaders import (
    get_or_create_basket,
    get_or_create_course,
    get_or_create_lookup,
    get_or_create_slot,
    get_or_create_term,
)


def load_all(session):
    course_cache = {}
    area_cache = {}

    # 1. Lookup tables
    for code, desc in COURSE_TYPES.items():
        get_or_create_lookup(session, CourseType, code, desc)
    for code, desc in COURSE_NATURES.items():
        get_or_create_lookup(session, CourseNature, code, desc)

    # 2. Shared Open Minor basket (term_id=None), created once up front
    #    so all four OPEN MINOR slots can point to the same row.
    om_basket = get_or_create_basket(
        session,
        "Open Minor Elective (OM) Basket",
        None,
        course_cache,
        area_cache,
        OM_SHARED,
    )

    # 3. Terms, their fixed courses, and their term-specific baskets
    for number, variant, label, slots in TERM_PLANS:
        term = get_or_create_term(session, number, variant, label)

        for slot in slots:
            course_id = None
            basket_id = None

            if "course" in slot:
                course = get_or_create_course(session, slot["course"], course_cache)
                course_id = course.id
            else:
                basket_key = slot["basket"]
                if basket_key == "OM_SHARED":
                    basket_id = om_basket.id
                else:
                    basket_name = f"{slot['display_name']} BASKET"
                    basket = get_or_create_basket(
                        session,
                        basket_name,
                        term.id,
                        course_cache,
                        area_cache,
                        BASKETS[basket_key],
                    )
                    basket_id = basket.id

            get_or_create_slot(
                session,
                term,
                slot["s_no"],
                slot.get("display_name"),
                course_id,
                basket_id,
                slot["type"],
                slot["nature"],
            )

    session.commit()


def run() -> None:
    """Create tables (if needed), load all curriculum data, and report counts."""
    upgrade_schema()  # single schema entrypoint (extension + tables + migrations)

    session = SessionLocal()
    try:
        load_all(session)
        print("Load complete.")

        # quick sanity check
        n_courses = session.query(Course).count()
        n_terms = session.query(Term).count()
        n_baskets = session.query(ElectiveBasket).count()
        n_options = session.query(BasketOption).count()
        n_slots = session.query(TermSlot).count()
        print(
            f"courses={n_courses} terms={n_terms} baskets={n_baskets} "
            f"basket_options={n_options} term_slots={n_slots}"
        )
    finally:
        session.close()
