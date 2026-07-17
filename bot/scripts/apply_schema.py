"""One-off script: apply schema.sql and seed spaces rows against DATABASE_URL.
Run manually: python scripts/apply_schema.py
"""
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

SPACES_SEED = [
    ("WorkHub Cyber City", "Gurgaon", "Cyber City", 300, 120, 8000, "Dedicated Desk"),
    ("WorkHub DLF Phase 3", "Gurgaon", "DLF Phase 3", 500, 340, 7500, "Managed Office"),
    ("Stylework Nehru Place", "Delhi", "Nehru Place", 200, 60, 9000, "Private Cabin"),
    ("Stylework Connaught Place", "Delhi", "Connaught Place", 150, 40, 12000, "Private Cabin"),
    ("WorkHub Koramangala", "Bangalore", "Koramangala", 400, 180, 8500, "Dedicated Desk"),
    ("Stylework Whitefield", "Bangalore", "Whitefield", 600, 410, 7000, "Managed Office"),
    ("WorkHub Andheri East", "Mumbai", "Andheri East", 250, 90, 10000, "Dedicated Desk"),
    ("Stylework BKC", "Mumbai", "BKC", 180, 20, 15000, "Private Cabin"),
    ("WorkHub Hitech City", "Hyderabad", "Hitech City", 350, 200, 6500, "Managed Office"),
    ("Stylework Baner", "Pune", "Baner", 220, 100, 6000, "Dedicated Desk"),
]


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    schema_sql = (Path(__file__).parent.parent / "schema.sql").read_text()

    conn = await asyncpg.connect(database_url)
    try:
        existing = await conn.fetchval(
            "SELECT to_regclass('public.leads')"
        )
        if existing is not None:
            print("Schema already applied (leads table exists) — skipping DDL.")
        else:
            async with conn.transaction():
                await conn.execute(schema_sql)
            print("Schema applied: users, companies, leads, interactions, spaces.")

        space_count = await conn.fetchval("SELECT count(*) FROM spaces")
        if space_count == 0:
            await conn.executemany(
                """
                INSERT INTO spaces
                    (name, city, locality, total_seats, available_seats, price_per_seat, space_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                SPACES_SEED,
            )
            print(f"Seeded {len(SPACES_SEED)} spaces rows.")
        else:
            print(f"spaces already has {space_count} rows — skipping seed.")

        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
            """
        )
        print("Tables now present:", [r["table_name"] for r in tables])
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
