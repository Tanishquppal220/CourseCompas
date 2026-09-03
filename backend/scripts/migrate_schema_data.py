import os
import re
import sys
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, engine
from app.models import (
    Base,
    Course,
    CoursePrerequisite,
    ElectiveBasket,
    Program,
    Term,
    TermCurriculum,
)


def clean_val(val: str) -> str:
    if not val:
        return ""
    # Remove markdown bold/italic/backslashes
    v = val.replace("**", "").replace("*", "").replace("\\", "").strip()
    return v


def parse_numeric(val: str, default=0.0):
    try:
        cleaned = clean_val(val)
        if not cleaned:
            return Decimal(str(default))
        return Decimal(cleaned)
    except Exception:  # noqa: BLE001
        return Decimal(str(default))


def parse_int(val: str, default=0):
    try:
        cleaned = clean_val(val)
        if not cleaned:
            return default
        return int(float(cleaned))
    except ValueError:
        return default


def parse_markdown_schema(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.split("\n")

    # 1. Parse Program metadata
    program_code = "P132"
    program_name = "B.Tech. (Computer Science and Engineering)"
    admission_year = 2024
    duration_years = 4

    for line in lines[:20]:
        m = re.search(r"Program Code & Name\s*:\s*([A-Za-z0-9]+)\s*::\s*([^*]+)", line)
        if m:
            program_code = clean_val(m.group(1))
            program_name = clean_val(m.group(2))
        m2 = re.search(
            r"Year of Admission\s*:\s*(\d+)\s+Duration in Years\s*:\s*(\d+)", line
        )
        if m2:
            admission_year = int(m2.group(1))
            duration_years = int(m2.group(2))

    program_data = {
        "ProgramCode": program_code,
        "ProgramName": program_name,
        "AdmissionYear": admission_year,
        "DurationYears": duration_years,
    }

    # Data collections
    courses_dict = {}  # CourseCode -> dict of attributes
    terms_list = []  # list of (term_dict, list_of_curriculum_items)
    baskets_list = []  # list of (basket_name, course_code, elective_area)
    prereqs_list = []  # list of (course_code, prereq_code)

    def extract_clean_cells(line: str):
        if not (line.strip().startswith("|") and line.strip().endswith("|")):
            return []
        cells = [clean_val(c) for c in line.strip()[1:-1].split("|")]
        return cells

    def filter_meaningful_cells(cells):
        return [c for c in cells if c != ""]

    term_regex = re.compile(
        r"\|\s*\*{0,2}(Term\s+[1-8][^\*\|]*)\*{0,2}\s*\|.*?\|\s*\*{0,2}(P132[^\*\|]*)\*{0,2}\s*\|",
        re.IGNORECASE,
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Check for Course Prerequisites
        if "**Course Prerequisites**" in line:
            curr = i + 1
            while curr < len(lines) and lines[curr].strip() != "| Course Type |":
                l = lines[curr].strip()
                if "CSE339" in l and "CAPSTONE PROJECT-I" in l:
                    prereqs_list.append(("CSE439", "CSE339"))
                    if "CSE339" not in courses_dict:
                        courses_dict["CSE339"] = {
                            "CourseCode": "CSE339",
                            "CourseTitle": "CAPSTONE PROJECT-I",
                            "L": 0,
                            "T": 0,
                            "P": 4,
                            "Credit": Decimal("2.0"),
                            "ContactHours": Decimal("4.0"),
                            "CourseType": "CR",
                            "CourseNature": "PRJ",
                        }
                    if "CSE439" not in courses_dict:
                        courses_dict["CSE439"] = {
                            "CourseCode": "CSE439",
                            "CourseTitle": "CAPSTONE PROJECT-II",
                            "L": 0,
                            "T": 0,
                            "P": 16,
                            "Credit": Decimal("8.0"),
                            "ContactHours": Decimal("16.0"),
                            "CourseType": "CR",
                            "CourseNature": "PRJ",
                        }
                curr += 1
            i = curr
            continue

        # Check for Term Table
        term_m = term_regex.search(line)
        if term_m:
            term_title = clean_val(term_m.group(1))
            term_code = clean_val(term_m.group(2))

            num_match = re.search(r"Term\s+(\d+)", term_title, re.IGNORECASE)
            term_num = int(num_match.group(1)) if num_match else 1

            if "industrial internship" in term_title.lower() or "P132A" in term_code:
                term_path = "A"
            else:
                term_path = "Common"

            term_dict = {
                "TermNumber": term_num,
                "TermPath": term_path,
            }
            term_curriculum = []

            curr = i + 1
            while curr < len(lines):
                row_str = lines[curr].strip()
                if not row_str.startswith("|"):
                    curr += 1
                    continue
                cells = filter_meaningful_cells(extract_clean_cells(row_str))
                if not cells:
                    curr += 1
                    continue
                if cells[0].upper() == "TOTAL":
                    curr += 1
                    break
                if (
                    "S.NO" in cells[0].upper()
                    or "COURSE CODE" in "".join(cells).upper()
                ):
                    curr += 1
                    continue
                if re.match(r"^:?-+:?$", cells[0]):
                    curr += 1
                    continue

                if re.match(r"^\d+$", cells[0]):
                    c_code = None
                    c_title = None
                    l_val, t_val, p_val, cr_val, ch_val = 0, 0, 0, 0.0, 0.0
                    c_type, c_nature = None, None

                    if re.match(r"^[A-Z]{2,4}\d{3,4}$", cells[1]):
                        c_code = cells[1]
                        c_title = cells[2]
                        if len(cells) >= 8:
                            l_val = parse_int(cells[3])
                            t_val = parse_int(cells[4])
                            p_val = parse_int(cells[5])
                            cr_val = parse_numeric(cells[6])
                            ch_val = parse_numeric(cells[7])
                        if len(cells) >= 9:
                            c_type = cells[8]
                        if len(cells) >= 10:
                            c_nature = cells[9]
                    else:
                        c_title = cells[1]
                        if len(cells) >= 7:
                            l_val = parse_int(cells[2])
                            t_val = parse_int(cells[3])
                            p_val = parse_int(cells[4])
                            cr_val = parse_numeric(cells[5])
                            ch_val = parse_numeric(cells[6])
                        if len(cells) >= 8:
                            c_type = cells[7]
                        if len(cells) >= 9:
                            c_nature = cells[8]

                    if c_code:
                        if c_code not in courses_dict:
                            courses_dict[c_code] = {
                                "CourseCode": c_code,
                                "CourseTitle": c_title,
                                "L": l_val,
                                "T": t_val,
                                "P": p_val,
                                "Credit": cr_val,
                                "ContactHours": ch_val,
                                "CourseType": c_type,
                                "CourseNature": c_nature,
                            }
                        else:
                            if not courses_dict[c_code]["CourseType"] and c_type:
                                courses_dict[c_code]["CourseType"] = c_type
                            if not courses_dict[c_code]["CourseNature"] and c_nature:
                                courses_dict[c_code]["CourseNature"] = c_nature
                        term_curriculum.append(
                            {"CourseCode": c_code, "PlaceholderName": None}
                        )
                    else:
                        term_curriculum.append(
                            {"CourseCode": None, "PlaceholderName": c_title}
                        )

                curr += 1

            terms_list.append((term_dict, term_curriculum))
            i = curr
            continue

        # Check for Basket Headers
        basket_m = re.match(r"^\*\*([^*]+BASKET[^*]*)\*\*$", line, re.IGNORECASE)
        is_om_basket = "Open Minor Elective (OM) Basket" in line
        if basket_m or is_om_basket:
            b_name = (
                clean_val(basket_m.group(1))
                if basket_m
                else "OPEN MINOR ELECTIVE (OM) BASKET"
            )
            curr = i + 1
            while curr < len(lines):
                row_str = lines[curr].strip()
                if row_str.startswith("**") and "BASKET" in row_str.upper():
                    break
                if "Open Minor Elective (OM) Basket" in row_str:
                    break
                if row_str.startswith(("| **Term", "| Term")):
                    break
                if (
                    "Course Prerequisites" in row_str
                    or "Category Description" in row_str
                ):
                    break
                if not row_str.startswith("|"):
                    curr += 1
                    continue

                cells = filter_meaningful_cells(extract_clean_cells(row_str))
                if not cells:
                    curr += 1
                    continue
                if cells[0].upper() == "TOTAL":
                    curr += 1
                    break
                if (
                    "S.NO" in cells[0].upper()
                    or "COURSE CODE" in "".join(cells).upper()
                ):
                    curr += 1
                    continue
                if re.match(r"^:?-+:?$", cells[0]):
                    curr += 1
                    continue
                if "Open Minor Elective" in cells[0]:
                    curr += 1
                    continue

                if re.match(r"^\d+$", cells[0]) and (
                    len(cells) >= 3 and re.match(r"^[A-Z]{2,4}\d{3,4}$", cells[1])
                ):
                    c_code = cells[1]
                    c_title = cells[2]
                    l_val = parse_int(cells[3]) if len(cells) > 3 else 0
                    t_val = parse_int(cells[4]) if len(cells) > 4 else 0
                    p_val = parse_int(cells[5]) if len(cells) > 5 else 0
                    cr_val = (
                        parse_numeric(cells[6]) if len(cells) > 6 else Decimal("0.0")
                    )
                    ch_val = (
                        parse_numeric(cells[7]) if len(cells) > 7 else Decimal("0.0")
                    )
                    elec_area = cells[8] if len(cells) > 8 else None

                    if c_code not in courses_dict:
                        courses_dict[c_code] = {
                            "CourseCode": c_code,
                            "CourseTitle": c_title,
                            "L": l_val,
                            "T": t_val,
                            "P": p_val,
                            "Credit": cr_val,
                            "ContactHours": ch_val,
                            "CourseType": None,
                            "CourseNature": None,
                        }

                    baskets_list.append(
                        {
                            "BasketName": b_name,
                            "CourseCode": c_code,
                            "ElectiveArea": elec_area,
                        }
                    )
                curr += 1

            i = curr
            continue

        i += 1

    return program_data, courses_dict, terms_list, baskets_list, prereqs_list


def migrate_data():
    file_path = os.path.join(
        Path(__file__).resolve().parent.parent, "data", "Schema.md"
    )
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Schema file not found at {file_path}")

    print("Parsing Schema.md...")
    prog_data, courses, terms, baskets, prereqs = parse_markdown_schema(file_path)

    print("Creating tables in PostgreSQL if not already present...")
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # Check if program exists
        existing_prog = (
            session.query(Program)
            .filter_by(
                ProgramCode=prog_data["ProgramCode"],
                AdmissionYear=prog_data["AdmissionYear"],
            )
            .first()
        )

        if existing_prog:
            program_obj = existing_prog
            print(
                f"Program already exists: {program_obj.ProgramCode} (ID: {program_obj.ProgramID})"
            )
        else:
            program_obj = Program(
                ProgramCode=prog_data["ProgramCode"],
                ProgramName=prog_data["ProgramName"],
                AdmissionYear=prog_data["AdmissionYear"],
                DurationYears=prog_data["DurationYears"],
            )
            session.add(program_obj)
            session.flush()
            print(
                f"Inserted Program: {program_obj.ProgramCode} (ID: {program_obj.ProgramID})"
            )

        # Insert / Upsert Courses
        print(f"Inserting/updating {len(courses)} courses...")
        for code, cdata in courses.items():
            existing_course = session.query(Course).filter_by(CourseCode=code).first()
            if not existing_course:
                new_course = Course(
                    CourseCode=code,
                    CourseTitle=cdata["CourseTitle"],
                    L=cdata["L"],
                    T=cdata["T"],
                    P=cdata["P"],
                    Credit=cdata["Credit"],
                    ContactHours=cdata["ContactHours"],
                    CourseType=cdata["CourseType"],
                    CourseNature=cdata["CourseNature"],
                )
                session.add(new_course)
            else:
                # Update attributes if they exist
                if cdata["CourseType"] and not existing_course.CourseType:
                    existing_course.CourseType = cdata["CourseType"]
                if cdata["CourseNature"] and not existing_course.CourseNature:
                    existing_course.CourseNature = cdata["CourseNature"]
        session.flush()

        # Insert Terms and Term Curriculum
        print(f"Processing {len(terms)} terms...")
        for term_meta, curr_items in terms:
            term_obj = (
                session.query(Term)
                .filter_by(
                    ProgramID=program_obj.ProgramID,
                    TermNumber=term_meta["TermNumber"],
                    TermPath=term_meta["TermPath"],
                )
                .first()
            )

            if not term_obj:
                term_obj = Term(
                    ProgramID=program_obj.ProgramID,
                    TermNumber=term_meta["TermNumber"],
                    TermPath=term_meta["TermPath"],
                )
                session.add(term_obj)
                session.flush()

            for item in curr_items:
                # check if curriculum item exists
                curr_exists = (
                    session.query(TermCurriculum)
                    .filter_by(
                        TermID=term_obj.TermID,
                        CourseCode=item["CourseCode"],
                        PlaceholderName=item["PlaceholderName"],
                    )
                    .first()
                )
                if not curr_exists:
                    tc = TermCurriculum(
                        TermID=term_obj.TermID,
                        CourseCode=item["CourseCode"],
                        PlaceholderName=item["PlaceholderName"],
                    )
                    session.add(tc)
        session.flush()

        # Insert Elective Baskets
        print(f"Inserting {len(baskets)} elective basket mappings...")
        for b in baskets:
            b_exists = (
                session.query(ElectiveBasket)
                .filter_by(
                    BasketName=b["BasketName"],
                    CourseCode=b["CourseCode"],
                    ElectiveArea=b["ElectiveArea"],
                )
                .first()
            )
            if not b_exists:
                session.add(
                    ElectiveBasket(
                        BasketName=b["BasketName"],
                        CourseCode=b["CourseCode"],
                        ElectiveArea=b["ElectiveArea"],
                    )
                )
        session.flush()

        # Insert Course Prerequisites
        print(f"Inserting {len(prereqs)} course prerequisites...")
        for course_code, prereq_code in prereqs:
            pr_exists = (
                session.query(CoursePrerequisite)
                .filter_by(CourseCode=course_code, PrereqCode=prereq_code)
                .first()
            )
            if not pr_exists:
                session.add(
                    CoursePrerequisite(CourseCode=course_code, PrereqCode=prereq_code)
                )
        session.commit()
        print("Migration completed successfully!")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_data()
