"""
seed.py — Demo data for the SitelineCRM (Stylework B2B Sales CRM) case study.

Seeds 1 manager + 2 reps and ~13 leads spread across every stage, several
cities, and a mix of small (dedicated-desk) to large (managed-office) deal
sizes, with a few interactions per lead and deliberately backdated
`last_activity_at` on some so the heat score, stale-lead nudges, and the
manager dashboard's stalled-leads list all have something real to show.

`spaces` inventory rows are seeded separately by `scripts/apply_schema.py`
(run once against a fresh DATABASE_URL) — this script only touches
users/companies/leads/interactions.

Usage:
  python seed.py --seed    Insert all demo data
  python seed.py --clear   Delete all demo data (only the rows this script created)
"""

import argparse
import asyncio
from datetime import datetime, timezone, timedelta

import db

# Fixed negative telegram_ids mark these as seed rows (real Telegram ids are
# positive) so --clear can find and delete exactly what --seed created,
# without touching real users who've since /start'd the bot.
MANAGER = {"telegram_id": -900001, "first_name": "Himanshu Rao", "email": "himanshu@stylework.city", "company": "Stylework", "role": "manager"}
REPS = [
    {"telegram_id": -900002, "first_name": "Priya Nair", "email": "priya@stylework.city", "company": "Stylework", "role": "rep"},
    {"telegram_id": -900003, "first_name": "Arjun Dev", "email": "arjun@stylework.city", "company": "Stylework", "role": "rep"},
]
SEED_TELEGRAM_IDS = [MANAGER["telegram_id"]] + [r["telegram_id"] for r in REPS]

now = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now - timedelta(days=n)


# Each lead: which rep (0=Priya, 1=Arjun), company/city/space profile, stage,
# a couple of interactions, and how many days ago the lead last moved (drives
# heat score + staleness). Deliberately spans every stage, a range of seat
# counts (4-desk deals to 500-seat managed offices), and several cities.
LEADS = [
    {
        "rep": 0, "company": "Zomato", "city": "Gurgaon", "contact_name": "Rohan Verma",
        "contact_role": "Facilities Manager", "phone": "9810000001", "stage": "Proposal",
        "seat_count": 200, "space_type": "Managed Office", "budget_per_seat": 7000,
        "est_deal_value": 1400000, "move_in_date": "next month", "source": "whatsapp_forward",
        "last_activity_days": 6,  # stale — sits in Proposal past the 3-day threshold
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 9,
             "raw": "Hey, we're looking to shift 200 people to a managed office in Gurgaon, Cyber City area preferably. Budget is around 7k per seat.",
             "summary": "Zomato needs 200-seat managed office in Gurgaon (Cyber City), ~₹7k/seat budget."},
            {"type": "voice_note", "days_ago": 6,
             "raw": "Bheja tha proposal Rohan ko, unhone bola internal review chal raha hai, next week tak update denge.",
             "summary": "Proposal sent, Zomato doing internal review, update expected next week."},
        ],
    },
    {
        "rep": 0, "company": "Razorpay", "city": "Bangalore", "contact_name": "Anita Rao",
        "contact_role": "Workplace Lead", "phone": "9810000002", "stage": "Negotiation",
        "seat_count": 40, "space_type": "Private Cabin", "budget_per_seat": 9000,
        "est_deal_value": 3600000, "move_in_date": "2026-08-15", "source": "voice_note",
        "last_activity_days": 1,
        "interactions": [
            {"type": "voice_note", "days_ago": 5,
             "raw": "Razorpay ka Anita, 40 seats private cabin chahiye Koramangala mein, demo bhi ho gaya achha laga unko.",
             "summary": "Razorpay wants 40-seat private cabin in Koramangala, demo went well."},
            {"type": "whatsapp_forward", "days_ago": 1,
             "raw": "We like the space but the per-seat price is a bit high for our budget. Can you do 8500 instead of 9000? We'd sign this week.",
             "summary": "Anita negotiating price down to ₹8500/seat, ready to sign this week if agreed."},
        ],
    },
    {
        "rep": 1, "company": "Cred", "city": "Mumbai", "contact_name": "Karan Mehta",
        "contact_role": "COO", "phone": "9810000003", "stage": "Closed-Won",
        "seat_count": 15, "space_type": "Dedicated Desk", "budget_per_seat": 10000,
        "est_deal_value": 900000, "move_in_date": "2026-07-20", "source": "screenshot",
        "last_activity_days": 2,
        "interactions": [
            {"type": "screenshot", "days_ago": 12,
             "raw": "[Screenshot of WhatsApp] Karan: need 15 dedicated desks near BKC for a new pod, moving in end of July.",
             "summary": "Cred needs 15 dedicated desks near BKC, moving in end of July."},
            {"type": "whatsapp_forward", "days_ago": 2,
             "raw": "Confirmed, we're going ahead. Please send the agreement, we'll sign by Friday.",
             "summary": "Deal closed — Cred confirmed, agreement being signed."},
        ],
    },
    {
        "rep": 1, "company": "Meesho", "city": "Bangalore", "contact_name": "Divya Shah",
        "contact_role": "Admin Head", "phone": "9810000004", "stage": "Closed-Lost",
        "seat_count": 60, "space_type": "Managed Office", "budget_per_seat": 6500,
        "est_deal_value": 4680000, "move_in_date": None, "source": "whatsapp_forward",
        "last_activity_days": 20,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 25,
             "raw": "We're comparing you against 2 other coworking chains for a 60-seat managed office in Whitefield.",
             "summary": "Meesho evaluating 60-seat managed office in Whitefield against 2 competitors."},
            {"type": "voice_note", "days_ago": 20,
             "raw": "Divya ne bola competitor ne better lock-in terms diye, hum unke saath ja rahe hain, sorry.",
             "summary": "Lost to a competitor over lock-in terms."},
        ],
    },
    {
        "rep": 0, "company": "Groww", "city": "Bangalore", "contact_name": "Ananya Kumar",
        "contact_role": "Head of Operations", "phone": "9810000005", "stage": "Qualified",
        "seat_count": 80, "space_type": "Managed Office", "budget_per_seat": 8000,
        "est_deal_value": 7680000, "move_in_date": "Q3 2026", "source": "whatsapp_forward",
        "last_activity_days": 4,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 4,
             "raw": "Hi, we're revisiting our office strategy — looking at 80 seats managed office, flexible on locality within Bangalore. Budget's healthy, around 8k/seat.",
             "summary": "Groww wants 80-seat managed office in Bangalore, flexible locality, ~₹8k/seat budget — qualified lead."},
        ],
    },
    {
        "rep": 1, "company": "Dukaan", "city": "Pune", "contact_name": "Nisha Joshi",
        "contact_role": "Co-founder", "phone": "9810000006", "stage": "Site Visit",
        "seat_count": 25, "space_type": "Private Cabin", "budget_per_seat": 6000,
        "est_deal_value": 1800000, "move_in_date": "next month", "source": "voice_note",
        "last_activity_days": 1,
        "interactions": [
            {"type": "voice_note", "days_ago": 8,
             "raw": "Nisha se baat hui, 25 seats cabin chahiye Baner mein, demo dekhna chahti hai.",
             "summary": "Dukaan wants 25-seat cabin in Baner, requested a demo."},
            {"type": "whatsapp_forward", "days_ago": 1,
             "raw": "Site visit confirmed for tomorrow 11am at the Baner location. Bringing 2 co-founders along.",
             "summary": "Site visit scheduled tomorrow 11am, 2 co-founders attending."},
        ],
    },
    {
        "rep": 0, "company": "Swiggy", "city": "Hyderabad", "contact_name": "Rahul Gupta",
        "contact_role": "Product Head", "phone": "9810000007", "stage": "Inquiry",
        "seat_count": 300, "space_type": "Managed Office", "budget_per_seat": 6500,
        "est_deal_value": 23400000, "move_in_date": None, "source": "screenshot",
        "last_activity_days": 0,
        "interactions": [
            {"type": "screenshot", "days_ago": 0,
             "raw": "[Screenshot] Rahul: exploring options for a 300-seat setup in Hyderabad, Hitech City preferred. Just gauging interest right now.",
             "summary": "Swiggy exploring 300-seat managed office in Hyderabad Hitech City — early inquiry."},
        ],
    },
    {
        "rep": 1, "company": "Fenix Apparel", "city": "Gurgaon", "contact_name": "Karan Malhotra",
        "contact_role": "Procurement Head", "phone": "9810000008", "stage": "Proposal",
        "seat_count": 12, "space_type": "Dedicated Desk", "budget_per_seat": 8000,
        "est_deal_value": 1152000, "move_in_date": "2026-09-01", "source": "whatsapp_forward",
        "last_activity_days": 7,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 10,
             "raw": "Proposal bheja Karan ko, 12 dedicated desks Gurgaon mein, unhone bola pricing thoda high hai.",
             "summary": "Sent proposal for 12 dedicated desks in Gurgaon — pricing pushback."},
            {"type": "whatsapp_forward", "days_ago": 7,
             "raw": "Discuss karenge next week negotiation call mein, abhi busy hain.",
             "summary": "Will discuss pricing in a negotiation call next week — currently quiet."},
        ],
    },
    {
        "rep": 0, "company": "Solstice Interiors", "city": "Mumbai", "contact_name": "Aditi Rao",
        "contact_role": "Owner", "phone": "9810000009", "stage": "Closed-Won",
        "seat_count": 8, "space_type": "Day Pass", "budget_per_seat": 500,
        "est_deal_value": 48000, "move_in_date": "2026-07-18", "source": "voice_note",
        "last_activity_days": 3,
        "interactions": [
            {"type": "voice_note", "days_ago": 3,
             "raw": "Aditi ne 8 day passes confirm kar diye, monthly package le rahi hain, chhota deal hai but confirmed.",
             "summary": "Aditi confirmed 8 day passes, small monthly package deal closed."},
        ],
    },
    {
        "rep": 1, "company": "Redwood Systems", "city": "Delhi", "contact_name": "Meera Iyer",
        "contact_role": "Ops Head", "phone": "9810000010", "stage": "Qualified",
        "seat_count": 50, "space_type": "Dedicated Desk", "budget_per_seat": 9500,
        "est_deal_value": 5700000, "move_in_date": None, "source": "whatsapp_forward",
        "last_activity_days": 2,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 2,
             "raw": "Comparing three vendors including you for a 50-seat setup near Nehru Place, Delhi.",
             "summary": "Redwood Systems comparing 3 vendors for 50-seat dedicated-desk setup near Nehru Place."},
        ],
    },
    {
        "rep": 0, "company": "Nimbus Cloud", "city": "Gurgaon", "contact_name": "Devansh Bhatt",
        "contact_role": "CTO", "phone": "9810000011", "stage": "Negotiation",
        "seat_count": 120, "space_type": "Managed Office", "budget_per_seat": 7500,
        "est_deal_value": 10800000, "move_in_date": "Q3 2026", "source": "whatsapp_forward",
        "last_activity_days": 5,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 11,
             "raw": "Nimbus needs 120 seats managed office, DLF Phase 3 area works well for our team.",
             "summary": "Nimbus Cloud needs 120-seat managed office in DLF Phase 3, Gurgaon."},
            {"type": "voice_note", "days_ago": 5,
             "raw": "Devansh ki team 10% discount maang rahi annual plan pe, sochna padega.",
             "summary": "Nimbus asking for 10% discount on annual plan — pending decision, quiet 5 days."},
        ],
    },
    {
        "rep": 1, "company": "Orion Traders", "city": "Pune", "contact_name": "Simran Kaur",
        "contact_role": "Business Dev", "phone": "9810000012", "stage": "Closed-Lost",
        "seat_count": 20, "space_type": "Dedicated Desk", "budget_per_seat": 5500,
        "est_deal_value": 1320000, "move_in_date": None, "source": "voice_note",
        "last_activity_days": 15,
        "interactions": [
            {"type": "voice_note", "days_ago": 18,
             "raw": "Simran bola budget issue hai unka, 20 desks chahiye the Pune mein but ab shayad nahi.",
             "summary": "Orion Traders had budget issues for 20-desk requirement in Pune."},
            {"type": "whatsapp_forward", "days_ago": 15,
             "raw": "Sorry, we've decided to hold off on the office move for now. Thanks for your time.",
             "summary": "Orion Traders decided to hold off — deal lost."},
        ],
    },
    {
        "rep": 0, "company": "Skyline Foods", "city": "Delhi", "contact_name": "Arjun Kapoor",
        "contact_role": "CTO", "phone": "9810000013", "stage": "Site Visit",
        "seat_count": 35, "space_type": "Private Cabin", "budget_per_seat": 9000,
        "est_deal_value": 3780000, "move_in_date": "next month", "source": "whatsapp_forward",
        "last_activity_days": 0,
        "interactions": [
            {"type": "whatsapp_forward", "days_ago": 4,
             "raw": "Comparing us with two other vendors, no budget discussed yet, wants a site visit first.",
             "summary": "Skyline Foods comparing vendors, requested a site visit before budget talk."},
            {"type": "whatsapp_forward", "days_ago": 0,
             "raw": "Site visit went great, Arjun's team loved the Connaught Place location. Deciding this week.",
             "summary": "Site visit completed, well received — decision expected this week."},
        ],
    },
]


async def seed():
    print("Seeding SitelineCRM demo data...\n")
    await db.init_pool()

    manager = await db.create_user(**MANAGER)
    print(f"Created manager: {manager['first_name']} (user_id={manager['id']})")

    rep_rows = []
    for rep in REPS:
        u = await db.create_user(**rep)
        rep_rows.append(u)
        print(f"Created rep: {u['first_name']} (user_id={u['id']})")
    print()

    pool = db._get_pool()

    for lead_data in LEADS:
        company = await db.find_or_create_company(lead_data["company"], city=lead_data["city"])
        rep = rep_rows[lead_data["rep"]]

        lead = await db.create_lead(
            contact_name=lead_data["contact_name"],
            company_id=company["id"],
            contact_role=lead_data["contact_role"],
            phone=lead_data["phone"],
            stage=lead_data["stage"],
            seat_count=lead_data["seat_count"],
            city=lead_data["city"],
            space_type=lead_data["space_type"],
            budget_per_seat=lead_data["budget_per_seat"],
            est_deal_value=lead_data["est_deal_value"],
            move_in_date=lead_data["move_in_date"],
            assigned_to=rep["id"],
            source=lead_data["source"],
        )

        for interaction in lead_data["interactions"]:
            row = await db.log_interaction(
                lead_id=lead["id"],
                type=interaction["type"],
                raw_content=interaction["raw"],
                ai_summary=interaction["summary"],
                user_id=rep["id"],
            )
            # log_interaction always stamps logged_at/last_activity_at as
            # now() — backdate both directly so heat score, "days quiet" on
            # the manager dashboard, and stale-lead nudges all reflect a
            # realistic spread instead of everything looking freshly touched.
            await pool.execute(
                "UPDATE interactions SET logged_at = $1 WHERE id = $2",
                days_ago(interaction["days_ago"]), row["id"],
            )

        await pool.execute(
            "UPDATE leads SET last_activity_at = $1 WHERE id = $2",
            days_ago(lead_data["last_activity_days"]), lead["id"],
        )

        print(f"  {lead_data['contact_name']} @ {lead_data['company']} "
              f"[{lead_data['stage']}] - {lead_data['seat_count']} seats, {lead_data['city']} OK")

    print(f"\nSeed complete! {len(LEADS)} leads across {len(rep_rows)} reps + 1 manager. "
          f"Open the dashboard to see the pipeline.")


async def clear():
    print("Clearing SitelineCRM demo data...\n")
    await db.init_pool()
    pool = db._get_pool()

    user_ids = [r["id"] for r in await pool.fetch(
        "SELECT id FROM users WHERE telegram_id = ANY($1::bigint[])", SEED_TELEGRAM_IDS
    )]
    if not user_ids:
        print("No seed users found — nothing to clear.")
        return

    lead_ids = [r["id"] for r in await pool.fetch(
        "SELECT id FROM leads WHERE assigned_to = ANY($1::bigint[])", user_ids
    )]
    if lead_ids:
        n = await pool.execute("DELETE FROM interactions WHERE lead_id = ANY($1::bigint[])", lead_ids)
        print(f"Deleted interactions: {n}")
        n = await pool.execute("DELETE FROM leads WHERE id = ANY($1::bigint[])", lead_ids)
        print(f"Deleted leads: {n}")

    company_names = list({ld["company"] for ld in LEADS})
    n = await pool.execute(
        "DELETE FROM companies WHERE name = ANY($1::text[]) "
        "AND id NOT IN (SELECT company_id FROM leads WHERE company_id IS NOT NULL)",
        company_names,
    )
    print(f"Deleted orphaned seed companies: {n}")

    n = await pool.execute("DELETE FROM users WHERE id = ANY($1::bigint[])", user_ids)
    print(f"Deleted seed users: {n}")

    print("\nClear complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SitelineCRM demo data seeder")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", action="store_true", help="Insert demo data")
    group.add_argument("--clear", action="store_true", help="Delete all demo data")
    args = parser.parse_args()

    if args.seed:
        asyncio.run(seed())
    elif args.clear:
        asyncio.run(clear())
