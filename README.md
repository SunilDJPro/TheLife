# TheLife

**A stern, no-nonsense life management platform that tracks, scores, and scrutinizes your daily activities to keep you accountable and aligned with your long-term goals.**

TheLife is not another passive productivity app. It actively prompts you to log your activities, scores your day with weighted analytics, and uses an LLM scrutinizer to call you out when you're drifting. Built for people who want to live deliberately — not on autopilot.

---

## v1.0 — Stable Release

### Features

**Dashboard & Calendar**
- Daily, weekly, and monthly calendar views with full navigation
- Real-time score display with component breakdowns (work, skills, fitness, personal, consistency)
- Catch-up prompts for unfilled time blocks — the platform reminds you to log
- "Today" quick-jump button across all views
- Activity log timeline with color-coded categories

**Activity Logging**
- Hourly activity logging across 10+ categories: Work, Skill Learning, Fitness, Meals & Nutrition, Commute, Social, Self-Care, Household, Entertainment, Spirituality, Creative
- Category-specific metadata fields (fitness intensity/sets/reps, meal type, commute mode)
- Quick-search for fast category/type selection
- Productivity self-rating per activity (1–5 scale)
- Recurring task management with direct "Log Session" flow — pre-fills form from task definition

**Work Management**
- Work profile with role, responsibilities, and working hours
- Project and deliverable tracking with status management (planned → in progress → completed)
- Work log entries with hours, blockers, and status tags
- Auto-syncs to the main activity timeline and dashboard calendar

**Skill Learning**
- One-at-a-time learning enforcement — max 2 active skills (configurable)
- Priority-based skill queue (Low → Critical)
- Multi-format resource tracking: Books, Coursera, Udemy, YouTube, Online Course (Other), Tutorials, Practice, Podcasts, Research Papers
- Book sessions: start/end page tracking with reading speed analytics (pages/hour)
- Course sessions: sections covered, section count, video timestamps
- All non-book resources support section tracking
- Progress tracking per resource with auto-updating completion percentages

**Entertainment**
- Pre-scheduling for movies, series, and gaming sessions
- Venue, duration, rating, and companion tracking
- Scheduled entertainment appears on the dashboard calendar
- Auto-syncs to activity timeline

**Scoring Engine**
- Weighted daily scoring formula out of 100:
  - Work efficiency (30%), Skill learning (25%), Fitness (15%), Personal time management (15%), Logging consistency (15%)
- Event-driven scoring — recalculates instantly on every activity log/edit/delete
- Weekly and monthly score aggregation (auto-computed)
- Server startup backfill — automatically scores any unscored past days (covers server-off gaps)
- 30-day trend chart with base vs. final score overlay

**AI Scrutinizer (LLM-Powered)**
- LLM reviews daily activity logs against user's long-term goals
- Adjusts score by ±30 points based on goal alignment
- Stern but constructive feedback with highlights and improvement suggestions
- Manual trigger per day or batch processing for all pending days
- Uses LiteLLM with Ollama (Gemma 3 12B) — runs locally, no data leaves your machine
- Clear status indicators: "Analytics" vs "AI ✓" badges per day

**User System**
- Admin-only account creation (multi-tenant ready backend)
- Profile with timezone, wake/sleep times, log interval configuration
- Long-term goals setting for AI alignment scoring
- OLED dark theme with Cyan, Emerald Green, and Dark Pink accents

**Technical**
- Django 5.1 with HTMX for responsive in-page interactions
- PostgreSQL for data persistence and scalability
- Unified activity timeline — work, skills, and entertainment auto-sync to a single ActivityLog model
- Multi-tenant architecture at the backend level
- Privacy-safe design — user activity data isolated per account

---

## Requirements

| Component | Version |
|-----------|---------|
| Python | 3.11+ |
| PostgreSQL | 14+ |
| Ollama | Latest (for AI Scrutinizer) |
| OS | Ubuntu 22.04+ / Debian 12+ |
| RAM | 8 GB minimum (16 GB recommended for LLM) |

### Python Dependencies

```
Django 5.1, psycopg2-binary, django-htmx, django-widget-tweaks,
litellm, whitenoise, python-dotenv, celery, redis (optional)
```

Full list in `requirements.txt`.

---

## Setup

### 1. Clone and Configure

```bash
git clone <repository-url> thelife
cd thelife
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
DB_NAME=thelife_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=ollama/gemma3:12b
```

### 3. Database Setup

```bash
sudo -u postgres createuser your_db_user --pwprompt
sudo -u postgres createdb thelife_db --owner=your_db_user
python manage.py migrate
python manage.py seed_categories    # Seeds activity categories and types
python manage.py createsuperuser    # Create your admin account
```

### 4. Run

```bash
python manage.py collectstatic --no-input
python manage.py runserver 0.0.0.0:8000
```

Access at `http://<your-ip>:8000`

### 5. AI Scrutinizer Setup (Optional)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve
ollama pull gemma3:12b    # ~7 GB download
```

The AI Scrutinizer is manually triggered from the Scores page — no background services required.

### Network Access

To access from other devices on the same network, ensure `ALLOWED_HOSTS` includes `*` or your server IP, and run with `0.0.0.0:8000`. For cross-network access (home ↔ office), consider [Tailscale](https://tailscale.com) for a private mesh VPN.

### Database Administration

Connect pgAdmin to your PostgreSQL instance for direct table access. Configure `postgresql.conf` (`listen_addresses = '*'`) and `pg_hba.conf` for remote connections.

---

## Usage

### Daily Workflow

1. **Morning** — Open TheLife. The dashboard shows unfilled time blocks from your wake time. Log what you've done.
2. **Throughout the day** — Log activities every 1–2 hours as prompted. Use "Log Activity" from dashboard or "Log Session" from recurring tasks.
3. **Work hours** — Log via Work Management for detailed project/deliverable tracking. Entries auto-sync to the dashboard.
4. **Skill sessions** — Log via Skills section with page numbers (books) or sections (courses). Reading speed and progress tracked automatically.
5. **Evening** — Review your daily score on the Scores page. Run AI Scrutinizer for goal-alignment feedback.

### Scoring

Your daily score is computed automatically after every activity log. It reflects how well you utilized your day across five dimensions. The AI Scrutinizer adds a qualitative layer — reviewing whether your activities actually align with your stated long-term goals, adjusting your score by up to ±30 points.

Weekly and monthly aggregates update automatically. Track trends on the 30-day chart.

### Skill Learning

The platform enforces focused learning. You can have at most 2 active skills. Queue others by priority and activate them when you complete or pause current ones. This is intentional — scattered learning leads nowhere.

---

## Roadmap

### v1.5 — Intelligence Layer

- **RAG-Powered Chatbot** — Retrieval-Augmented Generation over your last 3 months of activity data. Ask questions like "Am I on track for my goals?" or "What patterns do you see in my work hours?" and get data-grounded answers.
- **DNN/MLP Scoring & Anomaly Detection** — Deep neural network models trained on your activity patterns to detect habits, attention span trends, burnout signals, and productivity anomalies that rule-based scoring misses.
- **Agentic Task Scheduling** — AI agent that analyzes your working patterns, energy levels, and task priorities to auto-generate optimal daily schedules — removing the cognitive overhead of manual time management.

### v2.0 — Rust Rewrite

- **Full migration to Rust** for memory safety, performance, and concurrency. Fundamentally redesigned as a multi-tenant platform with a Super Admin management system.
- **C++ Neural Network Systems** for high-performance pattern recognition and guidance engines operating at scale — nuanced analytics beyond what Python ML frameworks offer in production.
- **Compliance-first architecture** built with **GDPR**, **ISO 27001** (Information Security), and **ISO 42001** (AI Management Systems) as foundational design constraints — not afterthoughts.

---

## Project Structure

```
thelife/
├── accounts/       # User auth, profiles, timezone, goals
├── activities/     # Core activity logging, recurring tasks, sync engine
├── dashboard/      # Home page, calendar views, catch-up prompts
├── entertainment/  # Movies, series, gaming pre-scheduling & logging
├── scoring/        # Daily/weekly/monthly scoring, LLM scrutinizer
├── skills/         # Skill queue, resources, session tracking
├── work/           # Projects, deliverables, work logs
├── templates/      # Django templates with HTMX partials
├── static/         # CSS (OLED dark theme), JS
└── thelife/        # Django project settings, URLs
```

---

## License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0).

You are free to use, modify, and distribute this software under the terms of the GPL. Any derivative work must also be distributed under the same license. See [LICENSE](LICENSE) for the full text.

---

*TheLife — Because your time is the only non-renewable resource you have.*