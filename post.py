"""
Generates an hourly UPSC-prep post using the Claude API and sends it to a
Telegram chat/channel via a bot. Designed to be run on a schedule (e.g. by
GitHub Actions) once per hour, 6 AM - 6 PM IST.

Required environment variables (set as GitHub Actions secrets):
  ANTHROPIC_API_KEY   - your Anthropic API key
  TELEGRAM_BOT_TOKEN  - your Telegram bot token (from BotFather)
  TELEGRAM_CHAT_ID    - the chat/channel ID to post to
"""

import os
import sys
import datetime
import requests
import anthropic

# ---- 1. Determine current hour (IST) and matching topic ----------------

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now_ist = datetime.datetime.now(IST)
hour = now_ist.hour
today_str = now_ist.strftime("%A, %d %B %Y")

SCHEDULE = {
    6:  "Daily current affairs headline relevant to UPSC (pick one real, recent, significant national/international event type topic area) and why it matters for the exam",
    7:  "A Polity concept (Indian Constitution, governance, parliamentary process, etc.)",
    8:  "A History fact (Ancient/Medieval/Modern Indian history) with exam relevance",
    9:  "A Geography concept (Indian or world physical/human geography)",
    10: "An Economy concept (Indian economy, budget, monetary policy, etc.)",
    11: "An Environment & Ecology topic (biodiversity, climate policy, conservation)",
    12: "A summary-style insight in the style of an editorial/opinion piece on a current issue",
    13: "A Science & Technology topic relevant to current affairs",
    14: "A Government scheme or policy (objective, beneficiaries, significance)",
    15: "An International Relations topic (bilateral relations, organizations, geopolitics)",
    16: "An Ethics case study or quote relevant to UPSC GS-4, PLUS a short motivational message for aspirants",
    17: "A quick quiz - one MCQ question with 4 options and the answer explained",
    18: "A revision/recap style summary tying together a key theme for the day",
}

# Subject title shown as the bold first line of each post, for branding
# and quick visual recognition of the slot.
TITLES = {
    6:  "📰 Current Affairs Byte",
    7:  "📜 Polity Byte",
    8:  "🏺 History Byte",
    9:  "🗺️ Geography Byte",
    10: "💰 Economy Byte",
    11: "🌿 Environment Byte",
    12: "🖋️ Editorial Byte",
    13: "🔬 Science & Tech Byte",
    14: "🏛️ Scheme Spotlight",
    15: "🌍 IR Byte",
    16: "🎯 Ethics & Motivation",
    17: "🧠 Quick Quiz",
    18: "🔁 Daily Revision",
}

# Marks weightage for the Mains-style PYQ + probable question added to each
# post. Hour 17 (quiz) is excluded since it's already question-format.
MARKS = {
    6: 10, 7: 15, 8: 10, 9: 15, 10: 15, 11: 10,
    12: 15, 13: 10, 14: 10, 15: 15, 16: 15, 18: 10,
}

if hour not in SCHEDULE:
    if os.environ.get("FORCE_TEST") == "true":
        # Manual test run - pick a representative topic regardless of hour
        hour = 7
        topic_instruction = SCHEDULE[hour]
        print(f"FORCE_TEST enabled - ignoring schedule, using hour {hour} topic for a test post.")
    else:
        print(f"Hour {hour} IST is outside the posting schedule (6-18). Exiting.")
        sys.exit(0)
else:
    topic_instruction = SCHEDULE[hour]

include_pyq = hour in MARKS
marks = MARKS.get(hour)
title = TITLES[hour]

# ---- 2. Generate the post using Claude ----------------------------------

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

system_prompt = """You are an expert UPSC (Indian Civil Services Exam) mentor \
who writes short, sharp, daily prep posts for a Telegram channel followed by \
serious aspirants. Every post must be:
- UNIQUE and SPECIFIC: include real facts, real names, real dates, real data \
where relevant - never generic filler or vague platitudes.
- HELPFUL: directly useful for UPSC Prelims/Mains preparation.
- INSPIRING where appropriate, but earn it through substance, not cliches.
- LIVELY TONE: write like an energetic, encouraging mentor talking directly \
to the aspirant - conversational, warm, a little punchy. Avoid dry textbook \
phrasing.
- CONCISE: keep the core explanation to 80-150 words.

FORMATTING RULES (Telegram Markdown):
- Start with the exact bold title line given to you, on its own line, \
followed by a blank line.
- Use short paragraphs (2-3 sentences max per block).
- For any list of points, use the bullet symbol "▪️" (not "-", "*" or "•").
- Leave a blank line between every distinct section (title, explanation, \
bullets, PYQ, probable question) so the post never looks cramped.
- EMOJI USE: 3-6 relevant emojis total across the whole post, but never more \
than 1-2 emojis on any single line - spread them out rather than clustering \
them together. They should add energy, not clutter.

ANTI-REPETITION RULE (critical):
- Do NOT reach for the most obvious, textbook, or frequently-cited \
example/fact/PYQ for the given topic - assume it has likely been used \
recently. Deliberately pick a less obvious but still well-known and \
accurate angle, sub-topic, or example within the topic area.
- Vary sentence openers and structure post-to-post; do not default to the \
same opening phrase pattern (e.g. always starting with "Did you know").
- Pull from across the full breadth of the UPSC syllabus and current \
affairs as of today's date rather than the first thing that comes to mind.

Output ONLY the final post text - no preamble, no "Here's a post", no quotes \
around it. Do NOT include any sign-off, footer, or channel name yourself - \
that will be added separately."""

pyq_block = f"""

After the main explanation, add exactly two more sections, each separated \
by a blank line:
📝 PYQ: Include one REAL UPSC Mains previous year question on this exact \
theme, and ALWAYS state the year explicitly in the format (UPSC Mains YYYY). \
Pick a question and year you are genuinely confident is accurate - draw \
from well-known, frequently-referenced PYQs on this theme so the year is \
reliable, but if you've likely used the single most famous one before, \
choose a different real PYQ on the same theme instead. Do not leave the \
year vague or generic.
🎯 Probable Question ({marks} marks): Write one well-crafted, exam-style \
probable question worth {marks} marks on today's theme, in authentic UPSC \
Mains phrasing (e.g. "Discuss...", "Critically examine...", "Analyse...")."""

user_prompt = f"""Today is {today_str}. Write today's {now_ist.strftime('%I %p')} \
Telegram post for UPSC aspirants.

Title line to use exactly as given: *{title}*

Topic for this hour: {topic_instruction}

Make it specific and non-generic - pick a particular fact, concept, or example \
rather than speaking in general terms, and follow the anti-repetition rule \
strictly.{pyq_block}"""

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=700,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
)

post_text = response.content[0].text.strip()
post_text = f"{post_text}\n\n— @ApexCCAcademy"

# ---- 3. Send to Telegram --------------------------------------------------

bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
resp = requests.post(
    telegram_url,
    data={
        "chat_id": chat_id,
        "text": post_text,
        "parse_mode": "Markdown",
    },
    timeout=30,
)

if resp.status_code != 200:
    print(f"Telegram send failed: {resp.status_code} {resp.text}")
    sys.exit(1)

print(f"Posted successfully for hour {hour} IST.")
print("---")
print(post_text)
