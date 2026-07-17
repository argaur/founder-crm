"""Throwaway end-to-end check of db.py against the live Neon database.

Run from bot/:  .venv/Scripts/python.exe scripts/verify_db.py

Creates a user, company, two leads (one active, one never-touched), logs an
interaction, exercises every read path, then deletes everything it created.
Exits 1 on any failure.
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


async def main():
    created = {"users": [], "companies": [], "leads": []}
    await db.init_pool()
    check("init_pool", True)

    try:
        telegram_id = random.randint(10**14, 10**15 - 1)
        user = await db.create_user(telegram_id, "Verify Bot", email="verify@example.com", role="rep")
        created["users"].append(user["id"])
        check("create_user", user["telegram_id"] == telegram_id and user["role"] == "rep",
              f"id={user['id']}")

        fetched_user = await db.get_user_by_telegram_id(telegram_id)
        check("get_user_by_telegram_id", fetched_user and fetched_user["id"] == user["id"])

        company = await db.find_or_create_company("__VERIFY_ACME__", industry="Tech", city="Gurgaon")
        created["companies"].append(company["id"])
        company_again = await db.find_or_create_company("__verify_acme__")
        check("find_or_create_company idempotent", company_again["id"] == company["id"],
              f"id={company['id']}")

        lead = await db.create_lead(
            "Verify O'Brien; DROP TABLE leads;--",
            company_id=company["id"],
            contact_role="Facilities Head",
            stage="Proposal",
            seat_count=1200,
            city="Gurgaon",
            space_type="Managed Office",
            budget_per_seat=7500,
            est_deal_value=9_000_000,
            move_in_date="next quarter",
            assigned_to=user["id"],
            source="whatsapp_forward",
        )
        created["leads"].append(lead["id"])
        check("create_lead", lead["stage"] == "Proposal" and lead["assigned_to"] == user["id"],
              f"id={lead['id']}")

        cold_lead = await db.create_lead(
            "Verify Untouched Lead",
            city="Pune",
            seat_count=4,
            est_deal_value=32_000,
            assigned_to=user["id"],
        )
        created["leads"].append(cold_lead["id"])
        check("create_lead (no activity)", cold_lead["stage"] == "Inquiry")

        try:
            await db.create_lead("Bad Stage Lead", stage="unknown")
            check("stage validation rejects 'unknown'", False)
        except ValueError:
            check("stage validation rejects 'unknown'", True)

        interaction = await db.log_interaction(
            lead["id"], "voice_note", "raw transcript here", "Client confirmed 1200 seats, Gurgaon.",
            user_id=user["id"],
        )
        check("log_interaction", interaction["lead_id"] == lead["id"])

        history = await db.get_interactions(lead["id"])
        check("get_interactions", len(history) == 1 and history[0]["id"] == interaction["id"])

        active = await db.get_lead_by_id(lead["id"])
        check("heat_score active big deal is Hot",
              active["heat_score"]["label"] == "Hot",
              f"score={active['heat_score']}")

        untouched = await db.get_lead_by_id(cold_lead["id"])
        check("heat_score never-touched lead is Cold (bug fix)",
              untouched["heat_score"]["label"] == "Cold",
              f"score={untouched['heat_score']}")

        check("heat_score big deal > small deal",
              active["heat_score"]["score"] > untouched["heat_score"]["score"],
              f"{active['heat_score']['score']} vs {untouched['heat_score']['score']}")

        found = await db.find_leads("o'brien; drop", assigned_to=user["id"])
        check("find_leads parameterized ILIKE (quote/injection-safe)",
              len(found) == 1 and found[0]["id"] == lead["id"])

        stale = await db.get_stale_leads(days=3, assigned_to=user["id"])
        stale_ids = {l["id"] for l in stale}
        check("get_stale_leads excludes fresh leads",
              lead["id"] not in stale_ids and cold_lead["id"] not in stale_ids,
              f"returned {len(stale)} rows for this user")

        pipeline = await db.get_all_leads(assigned_to=user["id"])
        check("get_all_leads has all 7 stage keys", list(pipeline.keys()) == db.STAGES)
        check("get_all_leads groups by stage",
              any(l["id"] == lead["id"] for l in pipeline["Proposal"])
              and any(l["id"] == cold_lead["id"] for l in pipeline["Inquiry"]))
        check("get_all_leads injects heat_score",
              all("heat_score" in l for stage in pipeline.values() for l in stage))

        reassigned = await db.assign_lead(cold_lead["id"], None)
        check("assign_lead (unassign)", reassigned["assigned_to"] is None)
        reassigned = await db.assign_lead(cold_lead["id"], user["id"])
        check("assign_lead (assign)", reassigned["assigned_to"] == user["id"])

        updated = await db.update_lead(cold_lead["id"], seat_count=6, city="Mumbai")
        check("update_lead whitelisted fields",
              updated["seat_count"] == 6 and updated["city"] == "Mumbai")

        won = await db.mark_won(lead["id"])
        check("mark_won sets Closed-Won", won["stage"] == "Closed-Won")
        lost = await db.mark_lost(cold_lead["id"])
        check("mark_lost sets Closed-Lost", lost["stage"] == "Closed-Lost")

        spaces = await db.get_all_spaces()
        check("get_all_spaces", isinstance(spaces, list), f"{len(spaces)} rows")

    finally:
        pool = db._get_pool()
        # interactions cascade with lead deletes (ON DELETE CASCADE)
        await pool.execute("DELETE FROM leads WHERE id = ANY($1::bigint[])", created["leads"])
        await pool.execute("DELETE FROM companies WHERE id = ANY($1::bigint[])", created["companies"])
        await pool.execute("DELETE FROM users WHERE id = ANY($1::bigint[])", created["users"])
        leftovers = await pool.fetchval(
            "SELECT count(*) FROM leads WHERE id = ANY($1::bigint[])", created["leads"]
        )
        check("cleanup left no rows behind", leftovers == 0)
        await db.close_pool()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
