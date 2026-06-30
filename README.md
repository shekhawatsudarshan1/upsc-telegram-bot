# UPSC Hourly Telegram Bot

Posts an automatic, unique UPSC-prep message to your Telegram chat every hour
from 6 AM to 6 PM IST, generated fresh each time by Claude.

## Setup (one-time)

1. **Create a new GitHub repo** (e.g. `upsc-telegram-bot`), Private is fine.
2. **Upload these 3 files**, keeping the same folder structure:
   - `post.py`
   - `requirements.txt`
   - `.github/workflows/hourly-post.yml`
3. **Add your secrets**: Repo → Settings → Secrets and variables → Actions →
   "New repository secret". Add all three:
   - `ANTHROPIC_API_KEY` → your key from console.anthropic.com
   - `TELEGRAM_BOT_TOKEN` → your bot token from BotFather
   - `TELEGRAM_CHAT_ID` → the chat/channel ID the bot should post to
4. **Test it manually**: Go to the "Actions" tab → "Hourly UPSC Telegram Post"
   workflow → "Run workflow" button → confirm. Check your Telegram chat for
   the post and the Actions log for any errors.
5. Once confirmed working, it'll run automatically on the built-in schedule —
   no further action needed.

## Notes

- GitHub's free tier includes 2,000 Actions minutes/month — this uses only a
  few minutes/day, well within the free limit.
- GitHub Actions schedules can occasionally run a few minutes late during
  high load periods; this is normal and on GitHub's end, not fixable from
  our side.
- To change topics per hour, edit the `SCHEDULE` dictionary in `post.py`.
- To pause posting, go to Actions tab → the workflow → "..." menu → "Disable
  workflow" (no need to delete anything).
