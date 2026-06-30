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

# ---- 2. Generate the post using Claude ----------------------------------

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

system_prompt = """You are an expert UPSC (Indian Civil Services Exam) mentor \
who writes short, sharp, daily prep posts for a Telegram channel followed by \
serious aspirants. Every post must be:
- UNIQUE and SPECIFIC: include real facts, real names, real dates, real data \
where relevant - never generic filler or vague platitudes.
- HELPFUL: directly useful for UPSC Prelims/Mains preparation.
- INSPIRING where appropriate, but earn it through substance, not cliches.
- CONCISE: 80-150 words, formatted cleanly for Telegram (short paragraphs, \
occasional bullet points using '-').
- EMOJI USE: minimal - at most ONE emoji in the entire post, and only if it \
fits naturally (e.g. in a heading). Do not force one in if nothing fits.
- Do NOT repeat the same examples/facts you'd typically default to - vary \
specifics each time, pulling from across the breadth of the UPSC syllabus \
and current affairs as of today's date.
Output ONLY the final post text - no preamble, no "Here's a post", no quotes \
around it. Do NOT include any sign-off, footer, or channel name yourself - \
that will be added separately."""

user_prompt = f"""Today is {today_str}. Write today's {now_ist.strftime('%I %p')} \
Telegram post for UPSC aspirants.

Topic for this hour: {topic_instruction}

Make it specific and non-generic - pick a particular fact, concept, or example \
rather than speaking in general terms."""

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=500,
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
