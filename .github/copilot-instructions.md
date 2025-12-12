# SydneyTrainsModBot Copilot Instructions

## Project Context
This repository contains the `SydneyTrainsModBot`, a Reddit moderation bot built with Python and PRAW.
It enforces daily posting limits based on user karma tiers to prevent spam in r/SydneyTrains.

## Architecture & Patterns
- **Core Logic**: `bot.py` handles the Reddit stream, karma checking, and database interactions.
- **Data Persistence**: Uses PostgreSQL to track user post timestamps.
  - **Docker Compose**: The `db` service handles the database, with data persisted in a Docker volume `postgres_data`.
- **Configuration**: Credentials are loaded from environment variables.
  - Local: `.env` file (via `python-dotenv`).
  - Docker/Production: Environment variables passed via `docker-compose.yml`.
- **Karma Tiers**: Logic defined in `TIERS` list (tuples of `max_karma, limit`).

## Development Workflow
- **Setup**:
  1. `pip install -r requirements.txt`
  2. Copy `.env.example` to `.env` and fill in Reddit API credentials.
- **Running Locally**: `python bot.py` (Requires a running Postgres instance accessible via env vars).
- **Running with Docker Compose**:
  1. Build & Run: `docker-compose up -d --build`
  2. Logs: `docker-compose logs -f`
- **CI/CD**:
  - GitHub Actions workflow (`.github/workflows/docker-publish.yml`) builds and pushes images to GHCR.
  - Triggers: Push to `develop` branch, or Release published on `main`.

## Coding Conventions
- **Testing**:
  - Mock `praw.Reddit` and `psycopg2` for unit tests.
  - Use `skip_existing=True` in `subreddit.stream.submissions` during dev to avoid processing old posts.
- **Error Handling**: Wrap API calls in `try/except` blocks to handle PRAW exceptions (network issues, API limits).
- **Database**: Always use parameterized queries (`%s`) to prevent injection.
- **Logging**: Currently uses `print()`. Future improvements should use the `logging` module.

## Critical Files
- `bot.py`: Main entry point.
- `docker-compose.yml`: Defines the multi-container application (Bot + Postgres).
- `.env`: Secrets file (ignored in git).
