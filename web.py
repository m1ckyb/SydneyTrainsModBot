from flask import Flask, render_template, request, redirect, session, url_for, Response, jsonify
import psycopg2
import os
from datetime import datetime
import praw
import uuid
import yaml
import shutil
import csv
import io

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key')

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'sydneytrains')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')

# Reddit Configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'web:SydneyTrainsModLog:v1.0')
REDDIT_REDIRECT_URI = os.getenv('REDDIT_REDIRECT_URI', 'http://localhost:5000/callback')
SUBREDDIT_NAME = os.getenv('SUBREDDIT_NAME', 'SydneyTrains')
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def get_reddit_auth_instance():
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        redirect_uri=REDDIT_REDIRECT_URI,
        user_agent=REDDIT_USER_AGENT
    )

def get_bot_reddit():
    """Returns a PRAW instance authenticated as the bot for performing actions."""
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=os.getenv('REDDIT_USERNAME'),
        password=os.getenv('REDDIT_PASSWORD')
    )

@app.route('/login')
def login():
    reddit = get_reddit_auth_instance()
    state = str(uuid.uuid4())
    session['oauth_state'] = state
    auth_url = reddit.auth.url(scopes=['identity', 'read'], state=state, duration='temporary')
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if state != session.get('oauth_state'):
        return "State mismatch. Please try again.", 400

    try:
        reddit = get_reddit_auth_instance()
        reddit.auth.authorize(code)
        user = reddit.user.me()
        
        # Check if user is a moderator of the subreddit
        # Note: We create a read-only instance or use the authenticated one to check
        is_mod = False
        for mod in reddit.subreddit(SUBREDDIT_NAME).moderator():
            if mod.name.lower() == user.name.lower():
                is_mod = True
                break
        
        if is_mod:
            session['user'] = user.name
            return redirect(url_for('index'))
        else:
            return f"Sorry, you must be a moderator of r/{SUBREDDIT_NAME} to view this page.", 403
            
    except Exception as e:
        return f"Authentication failed: {e}", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/approve/<item_id>')
def approve_item(item_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    try:
        bot = get_bot_reddit()
        if item_id.startswith('t1_') or item_id.startswith('t3_'):
            # It's a fullname (from Mod Queue)
            items = list(bot.info(fullnames=[item_id]))
            if items:
                items[0].mod.approve()
        else:
            # Legacy/Log ID (assume submission)
            submission = bot.submission(id=item_id)
            submission.mod.approve()
        
        return redirect(request.referrer or url_for('index'))
    except Exception as e:
        return f"Error approving item: {e}", 500

@app.route('/remove/<item_id>')
def remove_item(item_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    try:
        bot = get_bot_reddit()
        if item_id.startswith('t1_') or item_id.startswith('t3_'):
            items = list(bot.info(fullnames=[item_id]))
            if items:
                items[0].mod.remove(spam=False)
        else:
            submission = bot.submission(id=item_id)
            submission.mod.remove(spam=False)
            
        return redirect(request.referrer or url_for('index'))
    except Exception as e:
        return f"Error removing item: {e}", 500

@app.route('/ignore_reports/<item_id>')
def ignore_reports_item(item_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    try:
        bot = get_bot_reddit()
        if item_id.startswith('t1_') or item_id.startswith('t3_'):
            items = list(bot.info(fullnames=[item_id]))
            if items:
                items[0].mod.approve()
                items[0].mod.ignore_reports()
        else:
            submission = bot.submission(id=item_id)
            submission.mod.approve()
            submission.mod.ignore_reports()
            
        return redirect(request.referrer or url_for('index'))
    except Exception as e:
        return f"Error ignoring reports for item: {e}", 500

@app.route('/ban', methods=['POST'])
def ban_user():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    try:
        username = request.form.get('username')
        reason = request.form.get('reason')
        duration_str = request.form.get('duration')
        note = request.form.get('note')
        message = request.form.get('message')
        
        duration = None
        if duration_str:
            try:
                duration = int(duration_str)
                if not (1 <= duration <= 999):
                    return "Duration must be between 1 and 999 days.", 400
            except ValueError:
                return "Invalid duration format. Must be a number.", 400

        bot = get_bot_reddit()
        subreddit = bot.subreddit(SUBREDDIT_NAME)
        
        subreddit.banned.add(username, duration=duration, ban_reason=reason, note=note, ban_message=message)
        
        # Log this action
        conn = get_db_connection()
        cur = conn.cursor()
        details = f"Banned u/{username} for {duration or 'permanent'} days. Reason: {reason}"
        cur.execute("INSERT INTO mod_actions (action_type, username, details, timestamp, can_approve) VALUES (%s, %s, %s, %s, %s)",
                    ('BAN_USER', session.get('user'), details, datetime.now().timestamp(), False))
        conn.commit()
        
        return redirect(url_for('modqueue'))
    except Exception as e:
        return f"Error banning user: {e}", 500

@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    action = request.form.get('action')
    item_ids = request.form.getlist('item_ids')
    reason = request.form.get('reason')
    
    bot = get_bot_reddit()
    
    try:
        if item_ids:
            items = list(bot.info(fullnames=item_ids))
            for item in items:
                if action == 'approve':
                    item.mod.approve()
                elif action == 'remove':
                    r = reason if reason else "Removed by moderator"
                    item.mod.remove(mod_note=r, spam=False)
                elif action == 'ignore_reports':
                    item.mod.approve()
                    item.mod.ignore_reports()
                
        return redirect(url_for('modqueue'))
    except Exception as e:
        return f"Error processing bulk action: {e}", 500

@app.route('/modqueue')
def modqueue():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    filter_type = request.args.get('type', 'all').lower()
    sort_order = request.args.get('sort', 'newest').lower()
    
    bot = get_bot_reddit()
    subreddit = bot.subreddit(SUBREDDIT_NAME)
    items = []
    
    try:
        queue_list = list(subreddit.mod.modqueue(limit=None))
        
        # Collect authors to fetch notes
        authors = set()
        for item in queue_list:
            if item.author:
                authors.add(item.author.name)
        
        # Fetch notes for these authors
        notes_map = {}
        if authors:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT username, note FROM user_notes WHERE username = ANY(%s)", (list(authors),))
            for row in cur.fetchall():
                notes_map[row[0]] = row[1]
            cur.close()
            conn.close()

        for item in queue_list:
            is_comment = item.fullname.startswith('t1_')
            
            if filter_type == 'submission' and is_comment:
                continue
            if filter_type == 'comment' and not is_comment:
                continue
                
            if is_comment:
                full_content = item.body
            else:
                full_content = f"{item.title}\n\n{item.selftext}" if item.selftext else item.title
            
            snippet = full_content
            if len(snippet) > 100: snippet = snippet[:97] + "..."
            
            author_name = item.author.name if item.author else '[deleted]'
            
            # Calculate total reports
            report_count = sum(r[1] for r in item.user_reports) + len(item.mod_reports)
            
            items.append({
                'id': item.fullname,
                'type': 'Comment' if is_comment else 'Submission',
                'author': author_name,
                'content': snippet,
                'full_content': full_content,
                'is_long': len(full_content) > 100,
                'reports': item.user_reports + item.mod_reports,
                'report_count': report_count,
                'created': datetime.fromtimestamp(item.created_utc).strftime('%Y-%m-%d %H:%M'),
                'created_utc': item.created_utc,
                'permalink': f"https://reddit.com{item.permalink}",
                'user_note': notes_map.get(author_name)
            })
            
        # Sort items
        items.sort(key=lambda x: x['created_utc'], reverse=(sort_order == 'newest'))
    except Exception as e:
        return f"Error fetching mod queue: {e}", 500

    return render_template('modqueue.html', items=items, user=session.get('user'), current_filter=filter_type, current_sort=sort_order)

@app.route('/modmail')
def modmail():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    state = request.args.get('state', 'all')
    
    bot = get_bot_reddit()
    subreddit = bot.subreddit(SUBREDDIT_NAME)
    conversations = []
    
    try:
        conv_list = list(subreddit.modmail.conversations(state=state, limit=50))
        
        # Collect participants to check for notes
        participants = set()
        for conv in conv_list:
            if conv.participant:
                participants.add(conv.participant.name)
        
        notes_map = {}
        if participants:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT username FROM user_notes WHERE username = ANY(%s)", (list(participants),))
            for row in cur.fetchall():
                notes_map[row[0]] = True
            cur.close()
            conn.close()

        for conv in conv_list:
            participant_name = conv.participant.name if conv.participant else '[deleted]'
            conversations.append({
                'id': conv.id,
                'subject': conv.subject,
                'participant': participant_name,
                'last_updated': datetime.fromisoformat(conv.last_updated.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M'),
                'is_highlighted': conv.is_highlighted,
                'num_messages': conv.num_messages,
                'state': conv.state,
                'has_note': notes_map.get(participant_name, False)
            })
    except Exception as e:
        return f"Error fetching modmail: {e}", 500

    return render_template('modmail.html', conversations=conversations, user=session.get('user'), current_state=state)

@app.route('/modmail/<conversation_id>')
def modmail_conversation(conversation_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    bot = get_bot_reddit()
    subreddit = bot.subreddit(SUBREDDIT_NAME)
    
    try:
        conv = subreddit.modmail(conversation_id)
        messages = []
        for msg in conv.messages:
            messages.append({
                'author': msg.author.name if msg.author else '[deleted]',
                'body': msg.body_markdown,
                'date': datetime.fromisoformat(msg.date.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M'),
                'is_internal': msg.is_internal
            })
            
        return render_template('modmail_conversation.html', conversation=conv, messages=messages, user=session.get('user'))
    except Exception as e:
        return f"Error fetching conversation: {e}", 500

@app.route('/modmail/reply', methods=['POST'])
def modmail_reply():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    conversation_id = request.form.get('conversation_id')
    body = request.form.get('body')
    is_internal = request.form.get('is_internal') == 'on'
    
    bot = get_bot_reddit()
    conv = bot.subreddit(SUBREDDIT_NAME).modmail(conversation_id)
    conv.reply(body, internal=is_internal)
    
    return redirect(url_for('modmail_conversation', conversation_id=conversation_id))

@app.route('/modmail/archive/<conversation_id>', methods=['POST'])
def modmail_archive(conversation_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    bot = get_bot_reddit()
    conv = bot.subreddit(SUBREDDIT_NAME).modmail(conversation_id)
    conv.archive()
    
    return redirect(request.referrer or url_for('modmail'))

@app.route('/modmail/unarchive/<conversation_id>', methods=['POST'])
def modmail_unarchive(conversation_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    
    bot = get_bot_reddit()
    conv = bot.subreddit(SUBREDDIT_NAME).modmail(conversation_id)
    conv.unarchive()
    
    return redirect(request.referrer or url_for('modmail'))

@app.route('/config', methods=['GET', 'POST'])
def config():
    if not session.get('user'):
        return redirect(url_for('login'))

    file_type = request.args.get('file', 'automod')
    allowed_files = {
        'automod': 'automod.yaml',
        'tiers': 'tiers.yaml'
    }
    if file_type not in allowed_files:
        return "Invalid file type", 400
    config_path = allowed_files[file_type]

    if request.method == 'POST':
        new_content = request.form.get('content')
        try:
            # Validate YAML
            yaml.safe_load(new_content)
            
            # Create backup
            if os.path.exists(config_path):
                shutil.copy(config_path, config_path + '.bak')
            
            # Save file
            with open(config_path, 'w') as f:
                f.write(new_content)
            
            return redirect(url_for('config', file=file_type))
        except yaml.YAMLError as e:
            return f"Invalid YAML format: {e}", 400
        except Exception as e:
            return f"Error saving config: {e}", 500

    try:
        with open(config_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        content = f"# {config_path} not found"
        
    backup_exists = os.path.exists(config_path + '.bak')
    return render_template('config.html', content=content, user=session.get('user'), backup_exists=backup_exists, current_file=file_type)

@app.route('/restore_config', methods=['POST'])
def restore_config():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    file_type = request.args.get('file', 'automod')
    allowed_files = {
        'automod': 'automod.yaml',
        'tiers': 'tiers.yaml'
    }
    if file_type not in allowed_files:
        return "Invalid file type", 400
    config_path = allowed_files[file_type]
    backup_path = config_path + '.bak'
    
    if os.path.exists(backup_path):
        try:
            shutil.copy(backup_path, config_path)
        except Exception as e:
            return f"Error restoring config: {e}", 500
            
    return redirect(url_for('config', file=file_type))

@app.route('/export_csv')
def export_csv():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if search_query:
        search_pattern = f"%{search_query}%"
        cur.execute('SELECT * FROM mod_actions WHERE username ILIKE %s OR action_type ILIKE %s ORDER BY timestamp DESC', (search_pattern, search_pattern))
    else:
        cur.execute('SELECT * FROM mod_actions ORDER BY timestamp DESC')
    
    actions = cur.fetchall()
    cur.close()
    conn.close()
    
    def generate():
        data = io.StringIO()
        w = csv.writer(data)
        
        # Write header
        w.writerow(('ID', 'Action Type', 'Username', 'Details', 'Time', 'Submission ID', 'Can Approve'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)
        
        for a in actions:
            dt = datetime.fromtimestamp(a[4]).strftime('%Y-%m-%d %H:%M:%S')
            # Schema: id, action_type, username, details, timestamp, submission_id, can_approve
            w.writerow((a[0], a[1], a[2], a[3], dt, a[5] if len(a) > 5 else '', a[6] if len(a) > 6 else True))
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=mod_log.csv"})

@app.route('/stats')
def stats():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Date filtering
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date and end_date:
        # Filtered Stats
        cur.execute('''
            SELECT action_type, COUNT(*) FROM mod_actions 
            WHERE to_timestamp(timestamp) >= %s::date AND to_timestamp(timestamp) < %s::date + interval '1 day'
            GROUP BY action_type ORDER BY COUNT(*) DESC
        ''', (start_date, end_date))
        type_data = cur.fetchall()

        cur.execute('''
            SELECT to_char(to_timestamp(timestamp), 'YYYY-MM-DD') as day, COUNT(*) 
            FROM mod_actions 
            WHERE to_timestamp(timestamp) >= %s::date AND to_timestamp(timestamp) < %s::date + interval '1 day'
            GROUP BY day 
            ORDER BY day ASC
        ''', (start_date, end_date))
        time_data = cur.fetchall()

        cur.execute('''
            SELECT username, COUNT(*) FROM mod_actions 
            WHERE to_timestamp(timestamp) >= %s::date AND to_timestamp(timestamp) < %s::date + interval '1 day'
            GROUP BY username ORDER BY COUNT(*) DESC LIMIT 10
        ''', (start_date, end_date))
        top_offenders = cur.fetchall()
    else:
        # Default Stats (All time for types, last 30 days for time)
        cur.execute('SELECT action_type, COUNT(*) FROM mod_actions GROUP BY action_type ORDER BY COUNT(*) DESC')
        type_data = cur.fetchall()
        
        cur.execute('''
            SELECT to_char(to_timestamp(timestamp), 'YYYY-MM-DD') as day, COUNT(*) 
            FROM mod_actions 
            WHERE timestamp > extract(epoch from now()) - 2592000 
            GROUP BY day 
            ORDER BY day ASC
        ''')
        time_data = cur.fetchall()

        cur.execute('SELECT username, COUNT(*) FROM mod_actions GROUP BY username ORDER BY COUNT(*) DESC LIMIT 10')
        top_offenders = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('stats.html', 
                           type_labels=[row[0] for row in type_data], 
                           type_values=[row[1] for row in type_data],
                           time_labels=[row[0] for row in time_data],
                           time_values=[row[1] for row in time_data],
                           user=session.get('user'),
                           start_date=start_date,
                           end_date=end_date,
                           top_offenders=top_offenders)

@app.route('/api/recent_actions')
def api_recent_actions():
    if not session.get('user'):
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM mod_actions ORDER BY timestamp DESC LIMIT 5')
    actions = cur.fetchall()
    cur.close()
    conn.close()

    formatted_actions = []
    for a in actions:
        dt = datetime.fromtimestamp(a[4]).strftime('%H:%M:%S')
        formatted_actions.append({
            'type': a[1],
            'user': a[2],
            'details': a[3],
            'time': dt
        })
    return jsonify(formatted_actions)

@app.route('/notes', methods=['GET', 'POST'])
def notes():
    if not session.get('user'):
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username').strip()
        
        if action == 'save':
            note = request.form.get('note')
            moderator = session.get('user')
            timestamp = datetime.now().timestamp()
            
            # Upsert note
            cur.execute('''
                INSERT INTO user_notes (username, note, timestamp, moderator)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) 
                DO UPDATE SET note = EXCLUDED.note, timestamp = EXCLUDED.timestamp, moderator = EXCLUDED.moderator
            ''', (username, note, timestamp, moderator))
            conn.commit()
            
        elif action == 'delete':
            cur.execute('DELETE FROM user_notes WHERE username = %s', (username,))
            conn.commit()
            
        return redirect(url_for('notes'))

    cur.execute('SELECT * FROM user_notes ORDER BY timestamp DESC')
    notes_data = cur.fetchall()
    cur.close()
    conn.close()
    
    formatted_notes = []
    for n in notes_data:
        # Schema: username, note, timestamp, moderator
        dt = datetime.fromtimestamp(n[2]).strftime('%Y-%m-%d %H:%M')
        formatted_notes.append({
            'username': n[0],
            'note': n[1],
            'time': dt,
            'moderator': n[3]
        })

    return render_template('notes.html', notes=formatted_notes, user=session.get('user'))

@app.route('/')
def index():
    user = session.get('user')
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()

    if page < 1:
        page = 1
    per_page = 50
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cur = conn.cursor()

    if search_query:
        search_pattern = f"%{search_query}%"
        cur.execute('SELECT COUNT(*) FROM mod_actions WHERE username ILIKE %s OR action_type ILIKE %s', (search_pattern, search_pattern))
        total_count = cur.fetchone()[0]
        cur.execute('SELECT * FROM mod_actions WHERE username ILIKE %s OR action_type ILIKE %s ORDER BY timestamp DESC LIMIT %s OFFSET %s', (search_pattern, search_pattern, per_page, offset))
    else:
        cur.execute('SELECT COUNT(*) FROM mod_actions')
        total_count = cur.fetchone()[0]
        cur.execute('SELECT * FROM mod_actions ORDER BY timestamp DESC LIMIT %s OFFSET %s', (per_page, offset))

    actions = cur.fetchall()
    cur.close()
    conn.close()

    formatted_actions = []
    for a in actions:
        # Schema: id, action_type, username, details, timestamp, submission_id, can_approve
        dt = datetime.fromtimestamp(a[4]).strftime('%Y-%m-%d %H:%M:%S')
        formatted_actions.append({
            'type': a[1],
            'user': a[2],
            'details': a[3],
            'time': dt,
            'submission_id': a[5] if len(a) > 5 else None,
            'can_approve': a[6] if len(a) > 6 else True
        })
    
    total_pages = (total_count + per_page - 1) // per_page
    if total_pages == 0:
        total_pages = 1
    
    return render_template('index.html', actions=formatted_actions, user=user, page=page, total_pages=total_pages, search=search_query, test_mode=TEST_MODE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)