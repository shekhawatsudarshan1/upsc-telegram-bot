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
import json
import datetime
import requests
import anthropic

HISTORY_FILE = "topic_history.json"
HISTORY_DAYS = 30

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

TITLE_NAMES = {
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

# The syllabus anchor shown right under the title, and given to Claude as a
# hard constraint so every topic stays traceable to an actual GS paper -
# not a standalone news trivia item with no static-syllabus hook.
GS_PAPERS = {
    6:  "GS Paper 2/3 — Current Affairs (state which static topic this links to)",
    7:  "GS Paper 2 — Indian Polity & Governance",
    8:  "GS Paper 1 — Indian History",
    9:  "GS Paper 1 — Geography",
    10: "GS Paper 3 — Indian Economy",
    11: "GS Paper 3 — Environment & Ecology",
    12: "GS Paper 2/3 — Current Issue (state which static topic this links to)",
    13: "GS Paper 3 — Science & Technology",
    14: "GS Paper 2 — Governance & Schemes",
    15: "GS Paper 2 — International Relations",
    16: "GS Paper 4 — Ethics",
    17: "Prelims — MCQ Practice",
    18: "Revision — Cross-cutting",
}

MARKS = {
    6: 10, 7: 15, 8: 10, 9: 15, 10: 15, 11: 10,
    12: 15, 13: 10, 14: 10, 15: 15, 16: 15, 18: 10,
}

if hour not in SCHEDULE:
    if os.environ.get("FORCE_TEST") == "true":
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
gs_paper = GS_PAPERS[hour]

# Build the time-stamped title, e.g. "📰 6 AM Current Affairs Byte".
# strftime('%I') gives a zero-padded hour (e.g. "06"); strip the leading
# zero so it reads "6 AM" not "06 AM".
time_str = now_ist.strftime("%I %p").lstrip("0")
name_parts = TITLE_NAMES[hour].split(" ", 1)  # [emoji, "rest of name"]
icon, rest_of_name = name_parts[0], name_parts[1]
title = f"{icon} {time_str} {rest_of_name}"
subject_key = rest_of_name  # e.g. "Polity Byte" - used to scope history lookups

# ---- 1b. Load topic history and prune anything older than HISTORY_DAYS ----

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            history = json.load(f)
        except json.JSONDecodeError:
            history = []
else:
    history = []

cutoff = now_ist - datetime.timedelta(days=HISTORY_DAYS)


def _entry_date(entry):
    return datetime.datetime.strptime(entry["date"], "%Y-%m-%d").replace(tzinfo=IST)


history = [e for e in history if _entry_date(e) >= cutoff]

# Only show the model themes from the SAME subject slot (e.g. past Polity
# Bytes when writing today's Polity Byte) - keeps the list short and relevant
# instead of dumping all 13 slots' worth of history into the prompt.
recent_same_subject = [e for e in history if e.get("subject") == subject_key]

if recent_same_subject:
    history_lines = "\n".join(f"- {e['theme']}" for e in recent_same_subject)
    history_block = f"""

Themes already covered in this slot over the last {HISTORY_DAYS} days - do \
NOT repeat any of these topics or exact themes, pick something genuinely \
different:
{history_lines}"""
else:
    history_block = ""

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
- CONCISE: keep the core explanation to 80-150 words. Do NOT expand this \
budget even to add depth - depth has to come from tighter writing, not \
more words.

SYLLABUS ANCHORING (critical):
- The topic must tie to a genuine, identifiable UPSC syllabus item, not a \
standalone news/trivia snippet with no conceptual anchor. If the hook is a \
current-affairs event, explicitly connect it back to the static syllabus \
concept it tests within the first two sentences - do not just narrate the \
news.
- Reject niche or overly obscure angles that a Prelims/Mains examiner would \
never realistically draw a question from. Stay within the mainstream \
UPSC-relevant scope of the topic, even while picking a less-repeated \
example within it.

DEPTH OVER DESCRIPTION (critical):
- Spend most of the word budget on analysis, not narration: why it matters, \
the static-dynamic linkage (how the current event connects to the \
underlying syllabus concept), causes/implications, or a brief comparison. \
Limit scene-setting/context to at most one sentence.
- Cut generic filler, throat-clearing, or restating the topic name - every \
sentence should teach something an aspirant can use.

FORMATTING RULES (Telegram Markdown):
- Line 1: the exact bold title line given to you.
- Line 2: the exact GS paper/syllabus tag given to you, in italics, small \
and unobtrusive (e.g. "_GS Paper 3 — Indian Economy_").
- Leave a blank line, then the core explanation.
- Use short paragraphs (2-3 sentences max per block).
- For any list of points, use the bullet symbol "▪️" (not "-", "*" or "•").
- Leave a blank line between every distinct section (title+tag, \
explanation, bullets, Prelims angle, PYQ, probable question) so the post \
never looks cramped.
- EMOJI USE: 3-6 relevant emojis total across the whole post, but never more \
than 1-2 emojis on any single line - spread them out rather than clustering \
them together. They should add energy, not clutter.

ANTI-REPETITION RULE (critical):
- Do NOT reach for the most obvious, textbook, or frequently-cited \
example/fact/PYQ for the given topic - assume it has likely been used \
recently. Deliberately pick a less obvious but still mainstream, accurate \
angle, sub-topic, or example within the topic area.
- Vary sentence openers and structure post-to-post; do not default to the \
same opening phrase pattern (e.g. always starting with "Did you know").
- Pull from across the full breadth of the UPSC syllabus and current \
affairs as of today's date rather than the first thing that comes to mind.

Output ONLY the final post text - no preamble, no "Here's a post", no quotes \
around it. Do NOT include any sign-off, footer, or channel name yourself - \
that will be added separately.

After the ENTIRE post (including PYQ/probable question sections), add one \
final line, on its own, in this EXACT machine-readable format and nothing \
else on that line:
THEME_TAG: <3-6 word summary of today's specific topic/theme>
This line is for internal tracking only and will be stripped before \
publishing - it must still be included every time."""

pyq_block = f"""

After the main explanation, add exactly three more short sections, each \
separated by a blank line:
📌 Prelims Angle: One crisp, specific fact/data-point/date from this topic \
phrased the way it would actually appear as a Prelims MCQ statement (e.g. \
"X is headquartered in Y" or "X Act was passed in YYYY") - one line only.
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
GS paper tag to use exactly as given (in italics): _{gs_paper}_

Topic for this hour: {topic_instruction}

Make it specific and non-generic - pick a particular fact, concept, or example \
rather than speaking in general terms. Follow the anti-repetition rule, the \
syllabus anchoring rule, and the depth-over-description rule strictly - stay \
within the 80-150 word core explanation even while adding analytical \
depth.{history_block}{pyq_block}"""

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=700,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
)

raw_text = response.content[0].text.strip()

# Split off the internal THEME_TAG line (last line) - never send it to Telegram.
lines = raw_text.splitlines()
theme = "Unspecified"
if lines and lines[-1].strip().upper().startswith("THEME_TAG:"):
    theme = lines[-1].split(":", 1)[1].strip()
    lines = lines[:-1]
# Also drop a trailing blank line left behind after removing the tag.
while lines and not lines[-1].strip():
    lines.pop()

post_text = "\n".join(lines).strip()
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

# ---- 4. Save today's theme to history for future 30-day dedup checks -----

history.append({
    "date": now_ist.strftime("%Y-%m-%d"),
    "hour": hour,
    "subject": subject_key,
    "theme": theme,
})

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(history, f, ensure_ascii=False, indent=2)

print(f"Saved theme to history: {theme}")
