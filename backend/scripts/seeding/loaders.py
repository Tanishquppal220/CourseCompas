"""Idempotent get-or-create helpers for curriculum seeding.

Every insert is keyed on its natural unique key (course code, term
number+variant, basket name+term, term_id+s_no, ...), so the seeder can be
re-run without creating duplicates.
"""

from app.models import (
    BasketOption,
    Course,
    ElectiveArea,
    ElectiveBasket,
    Term,
    TermSlot,
)

from .curriculum_data import COURSES


def get_or_create_lookup(session, model, code, description):
    obj = session.get(model, code)
    if obj is None:
        obj = model(code=code, description=description)
        session.add(obj)
        session.flush()
    return obj


def get_or_create_course(session, code, course_cache):
    if code in course_cache:
        return course_cache[code]
    obj = session.query(Course).filter_by(code=code).one_or_none()
    if obj is None:
        title, l, t, p, credit, contact = COURSES[code]
        obj = Course(
            code=code,
            title=title,
            lecture_hours=l,
            tutorial_hours=t,
            practical_hours=p,
            credits=credit,
            contact_hours=contact,
        )
        session.add(obj)
        session.flush()
    course_cache[code] = obj
    return obj


def get_or_create_area(session, name, area_cache):
    if name is None:
        return None
    if name in area_cache:
        return area_cache[name]
    obj = session.query(ElectiveArea).filter_by(name=name).one_or_none()
    if obj is None:
        obj = ElectiveArea(name=name)
        session.add(obj)
        session.flush()
    area_cache[name] = obj
    return obj


def get_or_create_term(session, number, variant, label):
    obj = session.query(Term).filter_by(number=number, variant=variant).one_or_none()
    if obj is None:
        obj = Term(number=number, variant=variant, label=label)
        session.add(obj)
        session.flush()
    return obj


def get_or_create_basket(session, name, term_id, course_cache, area_cache, options):
    """term_id=None means a shared basket (e.g. the Open Minor basket)."""
    obj = (
        session.query(ElectiveBasket)
        .filter_by(name=name, term_id=term_id)
        .one_or_none()
    )
    if obj is None:
        obj = ElectiveBasket(name=name, term_id=term_id)
        session.add(obj)
        session.flush()
        for i, (course_code, area_name) in enumerate(options, start=1):
            course = get_or_create_course(session, course_code, course_cache)
            area = get_or_create_area(session, area_name, area_cache)
            exists = (
                session.query(BasketOption)
                .filter_by(
                    basket_id=obj.id,
                    course_id=course.id,
                    elective_area_id=(area.id if area else None),
                )
                .one_or_none()
            )
            if exists is None:
                session.add(
                    BasketOption(
                        basket_id=obj.id,
                        course_id=course.id,
                        elective_area_id=(area.id if area else None),
                        s_no=i,
                    )
                )
    return obj


def get_or_create_slot(
    session, term, s_no, display_name, course_id, basket_id, type_code, nature_code
):
    obj = session.query(TermSlot).filter_by(term_id=term.id, s_no=s_no).one_or_none()
    if obj is None:
        obj = TermSlot(
            term_id=term.id,
            s_no=s_no,
            display_name=display_name,
            course_id=course_id,
            basket_id=basket_id,
            course_type_code=type_code,
            course_nature_code=nature_code,
        )
        session.add(obj)
    return obj
