# SydneyTrainsModBot

**SydneyTrainsModBot** is a Reddit moderation bot designed for r/SydneyTrains. Its primary goal is to enforce daily posting limits based on user karma tiers to prevent spam.

## Features

- **Karma-based Limits**: Enforces different posting limits based on a user's global karma (Link + Comment).
- **Automatic Removal**: Removes posts that exceed the daily limit.
- **Sticky Notifications**: Informs users why their post was removed via a sticky comment.
- **Moderator Exemption**: Moderators are exempt from posting limits.
- **Web Dashboard**:
  - **Activity Log**: View moderation logs, search history, and export CSVs.
  - **Mod Queue**: Manage reported posts/comments (Approve, Remove, Ban, Ignore Reports).
  - **Modmail**: Read, reply, and archive modmail conversations.
  - **User Notes**: Store internal notes about specific users.
  - **Stats**: Visualize removal reasons, activity over time, and top offenders.
  - **Config Editor**: Edit `automod.yaml` and `tiers.yaml` directly from the browser.
- **Test Mode**: Simulate bot actions without affecting live Reddit posts.
- **Devvit App**: Includes a scaffold for a Reddit Developer Platform app (in `devvit-app/`).
- **Dockerized**: Easy deployment using Docker Compose.

## Posting Rules

| Karma Range | Daily Limit |
|-------------|-------------|
| 0 - 250     | 1 post      |
| 251 - 500   | 2 posts     |
| 501+        | 4 posts     |

*Note: Moderators have unlimited posting rights.*

## Prerequisites

- Python 3.x
- PostgreSQL (or use the Docker service)
- A Reddit Account with a registered App (Script or Web app type). Ensure the Redirect URI is set to `http://localhost:5000/callback` for web login.

## Configuration

Create a `.env` file in the root directory and populate it with your credentials:

```ini
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT=script:SydneyTrainsLimitBot:v1.0 (by /u/YOUR_USERNAME)
SUBREDDIT_NAME=SydneyTrains
REDDIT_REDIRECT_URI=http://localhost:5000/callback

# Web App Config
FLASK_SECRET_KEY=change_this_to_a_random_string

# Database Config (Defaults shown)
DB_HOST=db
DB_NAME=sydneytrains
DB_USER=postgres
DB_PASSWORD=password

# Optional
TEST_MODE=true  # Set to true to simulate actions without removing posts
```

## Installation & Usage

### Option 1: Docker

This is the recommended method for both production and development.

#### Production (from Docker Image)
This uses the pre-built image from GitHub Container Registry as defined in `docker-compose.yml`.
```bash
docker-compose up -d
```

#### Development (from Source)
This builds the image locally using `docker-compose-dev.yml` and is ideal for development.
1. **Build and Run**:
   ```bash
   docker-compose -f docker-compose-dev.yml up -d --build
   ```

2. **View Logs** (for either method):
   ```bash
   docker-compose logs -f
   ```

3. **Access Web Dashboard** (for either method):
   Open [http://localhost:5000](http://localhost:5000) in your browser. Log in with your Reddit moderator account to view logs and edit configuration.

### Option 2: Local Development

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure PostgreSQL is running**:
   Make sure you have a Postgres instance running and update your `.env` file to point to `localhost` (or your DB host) instead of `db`.

3. **Run the Bot and Web App**:
   You will need to run these in separate terminals:
   
   *Terminal 1 (Bot):*
   ```bash
   python bot.py
   ```
   
   *Terminal 2 (Web):*
   ```bash
   python web.py
   ```

### Devvit App (Optional)

If you wish to use the Reddit Developer Platform:

1. **Install the Devvit CLI** (Global):
   ```bash
   npm install -g devvit
   ```
2. **Login to Reddit**:
   ```bash
   devvit login
   ```
3. **Navigate to the app directory**:
   ```bash
   cd devvit-app
   ```
4. **Install dependencies**:
   ```bash
   npm install
   ```
5. **Run locally**:
   ```bash
   devvit play
   ```
6. **Upload to Reddit**:
   ```bash
   devvit upload
   ```