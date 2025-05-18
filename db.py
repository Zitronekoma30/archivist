import sqlite3, uuid, datetime

conn = sqlite3.connect("messages.db", check_same_thread=False)
cur  = conn.cursor()

# ---------- schema ----------
cur.executescript("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT,
    username TEXT,
    content TEXT,
    attachment_urls TEXT,
    timestamp TEXT
);

CREATE TABLE IF NOT EXISTS groups (
    group_id  TEXT PRIMARY KEY,
    share_id  TEXT UNIQUE,
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS group_members (
    user_id  TEXT,
    group_id TEXT,
    joined_at TEXT,
    PRIMARY KEY (user_id, group_id)
);
""")
conn.commit()

# ---------- helpers ----------
def _now():   # short-hand ISO timestamp
    return datetime.datetime.utcnow().isoformat()

def create_group(group_id: str, creator_id: str) -> str:
    """Create a group+token; caller is auto-member."""
    share_id = uuid.uuid4().hex
    cur.execute("INSERT INTO groups VALUES (?,?,?,?)",
                (group_id, share_id, creator_id, _now()))
    cur.execute("INSERT INTO group_members VALUES (?,?,?)",
                (creator_id, group_id, _now()))
    conn.commit()
    return share_id

def get_share_id(group_id: str):
    row = cur.execute("SELECT share_id FROM groups WHERE group_id=?",
                      (group_id,)).fetchone()
    return row[0] if row else None

def join_group(user_id: str, group_id: str):
    cur.execute("INSERT OR IGNORE INTO group_members VALUES (?,?,?)",
                (user_id, group_id, _now()))
    conn.commit()

def is_member(user_id: str, group_id: str) -> bool:
    return cur.execute("""
        SELECT 1 FROM group_members
        WHERE user_id=? AND group_id=?""",
        (user_id, group_id)).fetchone() is not None

def user_groups(user_id: str):
    """(group, message_count) for every group the user joined."""
    return cur.execute("""
        SELECT g.group_id,
               (SELECT COUNT(*) FROM messages m WHERE m.group_id=g.group_id) AS n
        FROM group_members g
        WHERE g.user_id=?
        ORDER BY g.group_id""", (user_id,)).fetchall()

def insert_message(group_id, username, content, attachment_urls, ts):
    cur.execute("""INSERT INTO messages
                   (group_id, username, content, attachment_urls, timestamp)
                   VALUES (?,?,?,?,?)""",
                (group_id, username, content, attachment_urls, ts))
    conn.commit()

def clear_messages(group_id):
    cur.execute("DELETE FROM messages WHERE group_id=?", (group_id,))
    conn.commit()
    return cur.rowcount

def get_messages(group_id: str):
    """Return all messages in this group, oldest first."""
    return cur.execute(
        """SELECT username, content, attachment_urls, timestamp
           FROM messages
           WHERE group_id = ?
           ORDER BY timestamp""",
        (group_id,),
    ).fetchall()
