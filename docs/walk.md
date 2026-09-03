# Walkthrough: Schema Data Migration to PostgreSQL

Curriculum data from [backend/data/Schema.md](file:///home/tanishq/Projects/CourseCompass/backend/data/Schema.md) was transferred into the PostgreSQL database running via [docker-compose.yml](file:///home/tanishq/Projects/CourseCompass/docker-compose.yml), adhering strictly to the schema structure in [docs/dbml.md](file:///home/tanishq/Projects/CourseCompass/docs/dbml.md).

## Summary of Changes

1. **Database Models ([backend/app/models.py](file:///home/tanishq/Projects/CourseCompass/backend/app/models.py))**:
   - `Program` (`programs`): `ProgramID`, `ProgramCode`, `ProgramName`, `AdmissionYear`, `DurationYears`
   - `Course` (`courses`): `CourseCode`, `CourseTitle`, `L`, `T`, `P`, `Credit`, `ContactHours`, `CourseType`, `CourseNature`
   - `Term` (`terms`): `TermID`, `ProgramID`, `TermNumber`, `TermPath`
   - `TermCurriculum` (`term_curriculum`): `CurriculumID`, `TermID`, `CourseCode`, `PlaceholderName`
   - `ElectiveBasket` (`elective_baskets`): `BasketID`, `BasketName`, `CourseCode`, `ElectiveArea`
   - `CoursePrerequisite` (`course_prerequisites`): `CourseCode`, `PrereqCode`

2. **Database Connection Configuration ([backend/app/database.py](file:///home/tanishq/Projects/CourseCompass/backend/app/database.py))**:
   - Connects to local PostgreSQL by default (`postgresql://tanishq:tanishq@localhost:5432/coursecompass`) or via `LOCAL_DATABASE_URL` / `DATABASE_URL`.

3. **Migration & ETL Script ([backend/scripts/migrate_schema_data.py](file:///home/tanishq/Projects/CourseCompass/backend/scripts/migrate_schema_data.py))**:
   - Parses Markdown tables, headers, and metadata without data loss.
   - Creates the necessary tables in PostgreSQL.
   - Populates programs, courses, terms, curriculum items (with course codes and placeholders), elective baskets (with elective areas), and prerequisites.

## Verification & Results

### Table Counts in Database
| Table Name | Record Count |
| :--- | :--- |
| `programs` | **1** (`P132 - B.Tech. CSE`) |
| `courses` | **250** unique courses |
| `terms` | **10** (Terms 1–6 Common, Term 7 Course Work & Internship, Term 8 Course Work & Internship) |
| `term_curriculum` | **60** scheduled curriculum entries |
| `elective_baskets` | **287** basket-to-course mappings across 25 distinct elective baskets |
| `course_prerequisites` | **1** (`CSE439` requires `CSE339`) |

### Sample Database Verification Query
Term 1 curriculum verification:
```sql
SELECT p."ProgramCode", p."ProgramName", t."TermNumber", t."TermPath", c."CourseCode", c."CourseTitle", tc."PlaceholderName"
FROM terms t
JOIN programs p ON p."ProgramID" = t."ProgramID"
JOIN term_curriculum tc ON tc."TermID" = t."TermID"
LEFT JOIN courses c ON c."CourseCode" = tc."CourseCode"
WHERE t."TermNumber" = 1
ORDER BY tc."CurriculumID";
```
Output:
- Row 1: `CORE ELECTIVE 1` (Placeholder)
- Row 2: `CORE ELECTIVE 2` (Placeholder)
- Row 3: `CORE ELECTIVE 3` (Placeholder)
- Row 4: `CSE111` - `ORIENTATION TO COMPUTING-I`
- Row 5: `CSE326` - `INTERNET PROGRAMMING LABORATORY`
- Row 6: `INT108` - `PYTHON PROGRAMMING`
- Row 7: `MTH174` - `ENGINEERING MATHEMATICS`
- Row 8: `PES318` - `SOFT SKILLS-I`
