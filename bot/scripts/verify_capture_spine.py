"""Exercise the Telegram capture spine without Telegram.

Drives the REAL handler (`flows.forward_or_text_handler`) with a stubbed
Telegram transport, so everything downstream runs for real: user lookup,
`ai.extract_from_text`, the quality gate, `_save_capture` (find-or-create
company + lead, `log_interaction`), the confirmation card, and the
space-matching follow-up.

What this does NOT cover: the actual Telegram round-trip — polling, handler
registration order in `main.py`, and inline-keyboard callbacks. Those still
need one real message to the live bot.

It writes to whatever DATABASE_URL points at. Against production that means a
real lead, so the fixtures read as plausible coworking inquiries rather than
obvious test junk.

    python scripts/verify_capture_spine.py

It always writes; the SQL to remove what it created is printed at the end.
"""
import asyncio
import os
import sys
from types import SimpleNamespace

# Windows consoles default to cp1252, which cannot encode the rupee sign the
# confirmation card uses. Force UTF-8 so a display quirk can't masquerade as a
# handler failure.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
import flows  # noqa: E402

# Gaurav's real Telegram id (user 14) — the only account with a positive id.
TELEGRAM_ID = 5325155077

FIXTURES = [
    ("WhatsApp forward — full inquiry",
     "Hi, this is Meera Sharma from Anvil Analytics. We're a 45-person team "
     "looking to move out of our current office in Bangalore by the end of next "
     "month. We'd want a private cabin setup, budget is around 9500 per seat. "
     "Could you share what you have available in Koramangala or Indiranagar?"),
    ("WhatsApp forward — later-stage negotiation",
     "Spoke to Rohit Menon at Kestrel Logistics again this afternoon. They've "
     "seen the Pune space and liked it, 30 seats dedicated desks. He's pushing "
     "for 8000 a seat against our 8800 quote and wants to sign this week if we "
     "can meet him halfway. Sending the revised proposal tonight."),
]


class FakeMessage:
    """Captures what the bot would have sent instead of calling Telegram."""

    def __init__(self, text):
        self.text = text
        self.sent = []

    async def reply_text(self, text, **kwargs):
        self.sent.append({"text": text, "kwargs": kwargs})
        return SimpleNamespace(message_id=1)


def build(text):
    msg = FakeMessage(text)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=TELEGRAM_ID),
        message=msg,
        effective_chat=SimpleNamespace(id=TELEGRAM_ID),
    )
    ctx = SimpleNamespace(user_data={}, bot_data={}, chat_data={}, bot=None)
    return update, ctx, msg


async def main():
    await db.init_pool()
    created = []
    failures = 0
    try:
        user = await db.get_user_by_telegram_id(TELEGRAM_ID)
        if not user:
            print(f"FAIL: no user for telegram_id {TELEGRAM_ID} — the handler "
                  f"would reply 'not registered'.")
            return 1
        print(f"acting as: {user['first_name']} (id {user['id']}, {user['role']})\n")

        before = {i for s in (await db.get_all_leads()).values() for i in [l['id'] for l in s]}

        for label, text in FIXTURES:
            print(f"--- {label} ---")
            update, ctx, msg = build(text)
            try:
                await flows.forward_or_text_handler(update, ctx)
            except Exception as e:
                print(f"  HANDLER RAISED: {type(e).__name__}: {e}\n")
                failures += 1
                continue

            if not msg.sent:
                print("  FAIL: handler produced no reply at all\n")
                failures += 1
                continue

            for i, m in enumerate(msg.sent):
                kind = "card" if m["kwargs"].get("reply_markup") else "message"
                body = m["text"].replace("\\", "")
                print(f"  [{kind}] {body[:400]}")
                if m["kwargs"].get("reply_markup"):
                    print("         buttons: Looks good / Edit stage")
            print()

        after = await db.get_all_leads()
        now = {l['id']: l for s in after.values() for l in s}
        created = [lid for lid in now if lid not in before]
        print(f"leads created: {len(created)} {created}")
        for lid in created:
            l = now[lid]
            print(f"  #{lid} {l['contact_name']} — {l['stage']} — "
                  f"{l.get('seat_count')} seats — {l.get('city')} — "
                  f"heat {l['heat_score']['score']} ({l['heat_score']['label']})")

        if created:
            print("\nThese are real rows. db.py has no delete helper by design, so "
                  "remove them deliberately if you don't want them in the demo:")
            print(f"  DELETE FROM interactions WHERE lead_id IN "
                  f"({', '.join(str(i) for i in created)});")
            print(f"  DELETE FROM leads WHERE id IN "
                  f"({', '.join(str(i) for i in created)});")

        print(f"\nRESULT: {'PASS' if not failures else f'{failures} FAILURE(S)'}")
        return 1 if failures else 0
    finally:
        await db.close_pool()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
