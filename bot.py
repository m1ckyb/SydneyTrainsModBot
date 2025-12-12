import praw
import time
import psycopg2
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import re
import yaml

# Load environment variables
load_dotenv()

# ================= CONFIGURATION =================
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'script:SydneyTrainsLimitBot:v1.0 (by /u/YOUR_USERNAME)')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

SUBREDDIT_NAME = os.getenv('SUBREDDIT_NAME', 'SydneyTrains')

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'sydneytrains')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

# Moderators are automatically exempt from these limits.

# =================================================

def init_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (username TEXT, timestamp DOUBLE PRECISION)''')
    # Create table for moderation logs
    c.execute('''CREATE TABLE IF NOT EXISTS mod_actions
                 (id SERIAL PRIMARY KEY, 
                  action_type TEXT, username TEXT, details TEXT, timestamp DOUBLE PRECISION)''')
    
    # Migration: Add submission_id column if it doesn't exist
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='mod_actions' AND column_name='submission_id'")
    if not c.fetchone():
        c.execute("ALTER TABLE mod_actions ADD COLUMN submission_id TEXT")

    # Migration: Add can_approve column if it doesn't exist
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='mod_actions' AND column_name='can_approve'")
    if not c.fetchone():
        c.execute("ALTER TABLE mod_actions ADD COLUMN can_approve BOOLEAN DEFAULT TRUE")
    
    # Create table for user notes
    c.execute('''CREATE TABLE IF NOT EXISTS user_notes
                 (username TEXT PRIMARY KEY, note TEXT, timestamp DOUBLE PRECISION, moderator TEXT)''')

    conn.commit()
    return conn

def clean_old_posts(conn):
    """Removes entries older than 24 hours"""
    c = conn.cursor()
    cutoff = time.time() - 86400 # 24 hours in seconds
    c.execute("DELETE FROM posts WHERE timestamp < %s", (cutoff,))
    conn.commit()

def get_user_post_count(conn, username):
    c = conn.cursor()
    c.execute("SELECT count(*) FROM posts WHERE username = %s", (username,))
    return c.fetchone()[0]

def log_post(conn, username):
    c = conn.cursor()
    c.execute("INSERT INTO posts VALUES (%s, %s)", (username, time.time()))
    conn.commit()

def log_mod_action(conn, action_type, username, details, submission_id=None, can_approve=True):
    try:
        c = conn.cursor()
        c.execute("INSERT INTO mod_actions (action_type, username, details, timestamp, submission_id, can_approve) VALUES (%s, %s, %s, %s, %s, %s)",
                  (action_type, username, details, time.time(), submission_id, can_approve))
        conn.commit()
    except Exception as e:
        print(f"Failed to log action: {e}")

def get_tiers():
    default_tiers = [{'max_karma': 250, 'limit': 1}, {'max_karma': 500, 'limit': 2}, {'max_karma': float('inf'), 'limit': 4}]
    try:
        with open('tiers.yaml', 'r') as f:
            tiers = yaml.safe_load(f)
            if not tiers: return default_tiers
            return tiers
    except Exception as e:
        print(f"Error loading tiers.yaml: {e}. Using defaults.")
        return default_tiers

def get_limit_for_user(karma):
    tiers = get_tiers()
    for tier in tiers:
        max_karma = tier.get('max_karma', 0)
        limit = tier.get('limit', 1)
        if karma < max_karma:
            return limit
    return 4

def check_content_rules(conn, submission, subreddit):
    """Checks submission against automod rules. Returns True if removed."""
    
    # Load rules
    try:
        with open('automod.yaml', 'r') as f:
            rules = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading automod.yaml: {e}")
        return False

    # Prepare content for checking
    content_map = {
        'title': submission.title,
        'body': submission.selftext,
        'domain': submission.domain,
        'combined': f"{submission.title} {submission.selftext}"
    }

    for rule in rules:
        matched = False
        match_val = ""
        
        # Check triggers
        triggers = rule.get('triggers', {})
        for key, patterns in triggers.items():
            # Normalize patterns to list
            if not isinstance(patterns, list):
                patterns = [patterns]

            # Determine target field and mode
            target_fields = []
            mode = 'contains' # default
            
            if '(regex)' in key:
                mode = 'regex'
                key = key.replace(' (regex)', '')
            elif '(starts-with)' in key:
                mode = 'startswith'
                key = key.replace(' (starts-with)', '')
            
            # Handle combined keys like "title+body"
            keys = key.split('+')
            
            # Check patterns against fields
            for field in keys:
                text_to_check = content_map.get(field.strip(), '')
                if not text_to_check: continue

                for pattern in patterns:
                    if mode == 'regex':
                        if re.search(pattern, text_to_check, re.IGNORECASE):
                            matched = True
                            match_val = pattern
                            break
                    elif mode == 'startswith':
                        if text_to_check.lower().startswith(pattern.lower()):
                            matched = True
                            match_val = pattern
                            break
                    else: # contains/exact match for domains
                        if pattern.lower() in text_to_check.lower():
                            matched = True
                            match_val = pattern
                            break
                if matched: break
            if matched: break
        
        if matched:
            print(f"Triggered Rule: {rule['name']} on {submission.id}")
            
            # Perform Action
            action = rule.get('action', 'filter')
            is_spam = (action == 'spam')
            
            if TEST_MODE:
                print(f"[TEST MODE] Would remove {submission.id} (spam={is_spam}) due to {rule['name']}")
            else:
                submission.mod.remove(spam=is_spam, mod_note=rule['name'])

            # Send Notifications
            if 'message' in rule:
                msg = rule['message'].replace('{{kind}}', 'submission').replace('{{match}}', str(match_val))
                if TEST_MODE:
                    print(f"[TEST MODE] Would reply to {submission.id}: {msg.splitlines()[0]}...")
                else:
                    submission.reply(msg).mod.distinguish(sticky=True)
            
            # Log Action
            can_approve = rule.get('allow_approval', True)
            details = f"Match: {match_val}"
            action_type = f"RULE_{rule['name'].upper().replace(' ', '_')}"
            if TEST_MODE:
                action_type = f"TEST_{action_type}"
            log_mod_action(conn, action_type, str(submission.author), details, submission.id, can_approve)
            return True

    return False

def main():
    # Check for missing credentials
    if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD]):
        print("Error: Missing Reddit credentials. Please check your .env file.")
        return

    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD
    )
    
    subreddit = reddit.subreddit(SUBREDDIT_NAME)
    conn = init_db()
    
    print(f"Listening for new posts in /r/{SUBREDDIT_NAME}...")
    if TEST_MODE:
        print("!!! RUNNING IN TEST MODE - No actions will be taken on Reddit !!!")

    # skip_existing=True prevents it from checking old posts when you first start it
    for submission in subreddit.stream.submissions(skip_existing=True):
        try:
            author = submission.author
            
            # If author is deleted/missing, skip
            if not author:
                continue
                
            # Ignore mods
            if submission.author in subreddit.moderator():
                continue

            # 0. Check Content Rules (Spam, Links, Profanity)
            if check_content_rules(conn, submission, subreddit):
                continue

            # 1. Clean DB of old posts
            clean_old_posts(conn)

            # 2. Check Karma (Total Global Karma)
            # Note: Reddit API doesn't give easy access to subreddit-specific karma
            # without heavy processing, so this uses Global Karma (Link + Comment).
            try:
                # Force fetch user data
                author._fetch() 
                total_karma = author.link_karma + author.comment_karma
            except Exception as e:
                print(f"Could not fetch karma for {author}: {e}")
                total_karma = 0

            # 3. Determine Limit
            limit = get_limit_for_user(total_karma)
            
            # 4. Check how many posts they made in last 24h
            current_count = get_user_post_count(conn, author.name)

            print(f"New post by {author.name} (Karma: {total_karma}). Count: {current_count}. Limit: {limit}")

            if current_count >= limit:
                print(f" -> REMOVING post by {author.name}")
                
                if TEST_MODE:
                    print(f"[TEST MODE] Would remove post {submission.id} by {author.name}")
                    print(f"[TEST MODE] Would reply to {author.name}")
                else:
                    # Remove the post
                    submission.mod.remove(mod_note="Daily post limit exceeded")
                    
                    # Reply to user
                    reply_text = (
                        f"Hi /u/{author.name}, your post has been removed because you have reached your daily posting limit.\n\n"
                        f"Your account has **{total_karma} karma**, which limits you to **{limit} post(s)** per 24 hours.\n\n"
                        "Please try again tomorrow!"
                    )
                    submission.reply(reply_text).mod.distinguish(sticky=True)
                
                details = f"Karma: {total_karma}, Limit: {limit}"
                action_type = "REMOVE_LIMIT"
                if TEST_MODE:
                    action_type = f"TEST_{action_type}"
                log_mod_action(conn, action_type, author.name, details, submission.id)
            else:
                # Log the valid post
                log_post(conn, author.name)

        except Exception as e:
            print(f"Error processing post: {e}")

if __name__ == "__main__":
    main()
