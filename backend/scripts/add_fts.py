from sqlalchemy import text

from app.database import engine


def upgrade():
    with engine.begin() as conn:
        print("Adding fts to course_doc_chunks...")
        conn.execute(
            text("""
        ALTER TABLE course_doc_chunks 
        ADD COLUMN IF NOT EXISTS fts tsvector 
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(section_title, '') || ' ' || coalesce(content, ''))) STORED;
        """)
        )
        conn.execute(
            text("""
        CREATE INDEX IF NOT EXISTS ix_course_doc_chunks_fts ON course_doc_chunks USING GIN (fts);
        """)
        )

        print("Adding fts to benefit_chunks...")
        conn.execute(
            text("""
        ALTER TABLE benefit_chunks 
        ADD COLUMN IF NOT EXISTS fts tsvector 
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(section_title, '') || ' ' || coalesce(content, ''))) STORED;
        """)
        )
        conn.execute(
            text("""
        CREATE INDEX IF NOT EXISTS ix_benefit_chunks_fts ON benefit_chunks USING GIN (fts);
        """)
        )


if __name__ == "__main__":
    upgrade()
    print("Done!")
