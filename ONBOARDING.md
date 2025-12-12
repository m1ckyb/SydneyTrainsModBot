# SydneyTrainsModBot Onboarding & Context

## 1. Project Overview
**SydneyTrainsModBot** is a Reddit moderation bot for r/SydneyTrains.
**Goal**: Enforce daily posting limits based on user karma tiers to prevent spam.

## 2. Architecture
- **Language**: Python 3.x
- **Libraries**: `praw` (Reddit API), `psycopg2` (Database), `python-dotenv` (Config).
- **Database**: PostgreSQL.
  - Stores: `(username, timestamp)` in table `posts`.
  - Persistence: Docker volume `postgres_data`.
- **Deployment**: Docker Compose (Services: `bot`, `web`, `db`).
- **CI/CD**: GitHub Actions pushes images to GHCR on push to `develop` or release.

## 3. Logic & Rules
- **Karma Tiers**:
  - Configurable in `tiers.yaml`.
- **Enforcement**:
  - Scans stream of new submissions.
  - Checks global karma (Link + Comment).
  - Removes posts exceeding limit.
  - Replies with a sticky comment.
  - **Exceptions**: Moderators are exempt from limits.
- **Content Filters**: Defined in `automod.yaml`. Supports regex, domain checks, and custom actions.
- **Web Interface**: Displays logs and allows editing `automod.yaml` at `http://localhost:5000`. Requires Reddit Login (Mod only).

## 4. Development Workflow
- **Local Run**: `python bot.py` (Needs local Postgres).
- **Docker Run**: `docker-compose up --build`.
- **Testing**: Mock `praw` and `psycopg2`.
- **Test Mode**: Set `TEST_MODE=true` in `.env` to simulate actions (Dry Run).
- **Changelog**: Update `unreleased.md` when adding features or fixes.

## 5. Coding Conventions
- **Style**: PEP 8.
- **Auth**: OAuth2 via PRAW for web login.
- **Web**: Flask for UI, Jinja2 for templates.
- **DB Security**: Use parameterized queries (`%s`).
- **Error Handling**: Try/Except blocks for API calls.
- **Logging**: Currently `print()`, moving to `logging` module recommended.

## 6. Critical Files
- `bot.py`: Main logic.
- `docker-compose.yml`: Container orchestration.
- `.github/workflows/docker-publish.yml`: CI/CD.
- `web.py`: Web interface entry point.
- `automod.yaml`: Configuration for content rules.
- `tiers.yaml`: Configuration for karma limits.
- `unreleased.md`: Tracks upcoming changes.