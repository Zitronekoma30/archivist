import asyncio, sqlite3
from typing import Dict, Optional, List

import discord
from db import (
    create_group,
    get_share_id,
    join_group,
    is_member,
    user_groups,
    insert_message,
    clear_messages,
)

DATABASE_PATH = "messages.db"
active_shelves: Dict[str, str] = {}          # user_id -> current shelf


# ── helpers that run in a thread pool ─────────────────────────────────────────
def get_shelf_id_by_token(token: str) -> Optional[str]:
    with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
        row = conn.execute(
            "SELECT group_id FROM groups WHERE share_id=?", (token,)
        ).fetchone()
    return row[0] if row else None


def remove_member(user_id: str, shelf_id: str) -> None:
    with sqlite3.connect(DATABASE_PATH, check_same_thread=False) as conn:
        conn.execute(
            "DELETE FROM group_members WHERE user_id=? AND group_id=?",
            (user_id, shelf_id),
        )
        conn.commit()


# ── bot entry ────────────────────────────────────────────────────────────────
def run(token: str, domain: str) -> None:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        print(f"Logged in as {client.user} ({client.user.id})")

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author == client.user or message.guild:
            return

        uid   = str(message.author.id)
        text  = message.content.strip()
        ltext = text.lower()

        # ───────────── /shelf <name> ──────────────────────────────────────────
        if ltext.startswith("/shelf "):
            name = text[7:].strip()
            if not name:
                await message.channel.send("Usage: `/shelf <name>`")
                return

            share = get_share_id(name)
            if share is None:                                        # create
                share = create_group(name, uid)
                await message.channel.send(
                    f"🗄️ **New shelf** `{name}` created.\n"
                    f"🔗 Token: `{share}`  (others `/join {share}`)"
                )
            elif not is_member(uid, name):                           # exists
                await message.channel.send(
                    "🔒 You’re not on that shelf. "
                    "Ask for its token and `/join <token>` first."
                )
                return
            else:                                                    # switch
                await message.channel.send(
                    f"🗄️ Switched to shelf `{name}` (token `{share}`)"
                )

            active_shelves[uid] = name
            return

        # ───────────── /join <token> ─────────────────────────────────────────
        if ltext.startswith("/join "):
            token_val = text[6:].strip()
            if not token_val:
                await message.channel.send("Usage: `/join <token>`")
                return

            shelf_id = await asyncio.to_thread(get_shelf_id_by_token, token_val)
            if shelf_id is None:
                await message.channel.send("❓ Unknown or expired token.")
                return

            join_group(uid, shelf_id)
            active_shelves[uid] = shelf_id
            await message.channel.send(
                f"🔑 Joined shelf `{shelf_id}` — you can now `/shelf {shelf_id}`."
            )
            return

        # ───────────── /list ────────────────────────────────────────────────
        if ltext == "/list":
            shelves = user_groups(uid)        # (shelf, count)
            if not shelves:
                await message.channel.send("🙈 You’re not on any shelves yet.")
                return

            lines = []
            for sid, cnt in shelves:
                tok = get_share_id(sid)
                lines.append(f"`{sid}` – {cnt} msg(s) | token `{tok}`")
            await message.channel.send("📚 **Your shelves**\n" + "\n".join(lines))
            return

        # ───────────── /leave ───────────────────────────────────────────────
        if ltext == "/leave":
            sid = active_shelves.get(uid)
            if not sid:
                await message.channel.send("⚠️ No active shelf to leave.")
                return

            await asyncio.to_thread(remove_member, uid, sid)
            active_shelves.pop(uid, None)
            await message.channel.send(f"🚪 You left shelf `{sid}`.")
            return

        # ───────────── /link ────────────────────────────────────────────────
        if ltext == "/link":
            sid = active_shelves.get(uid)
            if not sid:
                await message.channel.send("⚠️ No active shelf. `/shelf <name>` first.")
                return
            await message.channel.send(f"🔗 {domain}/archive?token={get_share_id(sid)}")
            return

        # ───────────── /clear ───────────────────────────────────────────────
        if ltext == "/clear":
            sid = active_shelves.get(uid)
            if not sid:
                await message.channel.send("⚠️ No active shelf to clear.")
                return
            deleted = clear_messages(sid)
            await message.channel.send(f"🧹 Cleared {deleted} entries from `{sid}`.")
            return

        # ───────────── /help ────────────────────────────────────────────────
        if ltext == "/help":
            cur = active_shelves.get(uid, "none")
            await message.channel.send(
f"""🗂️ **Archivist Bot Help**

`/shelf <name>` – create or enter a shelf  
`/join <token>` – join a shelf from its token  
`/leave` – leave the current shelf  
`/list` – list your shelves, message counts & tokens  
`/link` – archive link for the current shelf  
`/clear` – delete all entries in the current shelf  
`/help` – show this help

**Current shelf:** `{cur}`"""
            )
            return

        # ───────────── regular DM ───────────────────────────────────────────
        sid = active_shelves.get(uid)

        # First‐time user: ask them to create a shelf
        if sid is None:
            shelves: List[tuple[str, int]] = user_groups(uid)
            if not shelves:
                await message.channel.send(
                    "👋 Hi! Create your first shelf with `/shelf <name>` "
                    "before sending messages."
                )
                return
            # User already has shelves but none chosen in this session
            sid = shelves[0][0]
            active_shelves[uid] = sid
            await message.channel.send(f"🗄️ Defaulting to your shelf `{sid}`.")

        insert_message(
            sid,
            str(message.author),
            message.content,
            ", ".join(a.url for a in message.attachments),
            message.created_at.isoformat(),
        )
        await message.add_reaction("📖")

    client.run(token)
