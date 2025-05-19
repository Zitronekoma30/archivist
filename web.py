from flask import Flask, request, abort
import sqlite3, html, re
from db import get_messages
from urllib.parse import urlparse

app = Flask(__name__)

IMG_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')

# ---------- helpers ----------------------------------------------------------

def _user_id(token: str) -> int | None:
    with sqlite3.connect("messages.db") as conn:
        row = conn.execute(
            'SELECT user_id FROM share_links WHERE share_id=?', (token,)
        ).fetchone()
    return row[0] if row else None

def _group_id(token: str) -> str | None:
    with sqlite3.connect("messages.db") as conn:
        row = conn.execute(
            "SELECT group_id FROM groups WHERE share_id=?", (token,)
        ).fetchone()
    return row[0] if row else None

def _preview(url: str) -> str:
    """Return an <img> tag for images, otherwise a normal link."""
    url = url.strip()
    return (
        f'<img src="{url}" loading="lazy" alt="" class="preview">'
        if urlparse(url).path.lower().endswith(IMG_EXTS)
        else f'<a href="{url}" target="_blank" rel="noopener">{html.escape(url)}</a>'
    )


_link_re = re.compile(r'https?://\S+')

def _linkify(text: str) -> str:
    """Escape HTML, replace links with previews, keep newlines."""
    esc = html.escape(text)
    esc = _link_re.sub(lambda m: _preview(m.group(0)), esc)
    return esc.replace("\n", "<br>")


# ---------- route ------------------------------------------------------------

@app.route("/archive")
def archive():
    token  = request.args.get("token") or abort(400)
    group  = _group_id(token)           or abort(404)

    cards = []
    for author, txt, atts, ts in get_messages(group):
        body = _linkify(txt or "")
        if atts:
            for url in atts.split(", "):
                body += "<br>" + _preview(url)

        cards.append(f"""
        <div class="card">
          <div class="meta">
            {html.escape(author)} @ {ts}
            <button class="copy-btn" title="Copy to clipboard">📋</button>
          </div>
          <div class="content">{body}</div>
        </div>""")
    
    return render_archive(cards)

def render_archive(cards):
    return f"""<!doctype html><html lang="en">
<head><meta charset="utf-8">
<title>The Archive</title>
<style>
* {{ box-sizing:border-box; }}
body {{
  margin:0;
  font-family:'Georgia',serif;
  background:var(--bg);
  color:var(--fg);
  transition:background .3s,color .3s;
}}

:root {{
  --bg:#f9f6f1;
  --fg:#2d1f14;
  --card-bg:#fff8f0;
  --card-shadow:rgba(0,0,0,.05);
  --accent:#6e4b2e;
}}
body.dark {{
  --bg:#1f1a17;
  --fg:#f4e9d8;
  --card-bg:#2a211c;
  --card-shadow:rgba(0,0,0,.3);
  --accent:#d2b48c;
}}

h1 {{
  text-align:center;
  margin:2rem 0 1rem;
  font-size:2.5rem;
  position:relative;
}}

#toggle-theme {{
  position:absolute;
  right:2rem;
  top:2rem;
  background:none;
  border:1px solid var(--fg);
  color:var(--fg);
  padding:.4rem .8rem;
  border-radius:5px;
  cursor:pointer;
  font-family:inherit;
}}

#search {{
  display:block;
  margin:0 auto 1.5rem;
  padding:.5rem .8rem;
  font-size:1rem;
  width:clamp(200px,50%,400px);
  border:1px solid var(--accent);
  border-radius:6px;
  background:var(--card-bg);
  color:var(--fg);
}}

.grid {{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
  gap:1.2rem;
  padding:1.5rem;
  max-width:1200px;
  margin:auto;
}}

.card {{
  background:var(--card-bg);
  border-radius:10px;
  padding:1rem;
  box-shadow:0 3px 8px var(--card-shadow);
  transition:transform .1s ease;
  overflow:hidden;           /* keep children inside */
}}
.card:hover {{ transform:scale(1.01); }}

.meta {{
  font-size:.85rem;
  color:var(--accent);
  margin-bottom:.6rem;
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:.5rem;
}}

.copy-btn {{
  border:0;
  background:transparent;
  font-size:1rem;
  cursor:pointer;
  color:var(--accent);
}}
.copy-btn:active {{ transform:scale(.9); }}

.content {{
  white-space:pre-wrap;
  line-height:1.5;
  overflow-wrap:anywhere;    /* long URLs/text won’t overflow */
  word-break:break-word;
}}

.preview {{
  max-width:100%;
  border-radius:4px;
  margin-top:.5rem;
  box-shadow:0 0 4px var(--card-shadow);
}}
</style>
</head><body>
<h1>The Archive <button id="toggle-theme" title="Toggle theme">🌓</button></h1>

<input type="search" id="search" placeholder="Search…">

<div class="grid">{''.join(cards)}</div>

<script>
// copy-to-clipboard
document.addEventListener('click', e => {{
  if (e.target.closest('.copy-btn')) {{
    const btn  = e.target.closest('.copy-btn');
    const card = btn.closest('.card');
    const txt  = card.querySelector('.content').innerText;
    navigator.clipboard.writeText(txt).then(() => {{
      btn.textContent = '✓';
      setTimeout(() => btn.textContent = '📋', 1500);
    }});
  }}
}});

// live search
const search = document.getElementById('search');
search.addEventListener('input', () => {{
  const q = search.value.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    c.style.display = c.innerText.toLowerCase().includes(q) ? '' : 'none';
  }});
}});

// theme toggle
const toggle = document.getElementById('toggle-theme');
const body   = document.body;
if (localStorage.getItem('theme') === 'dark') body.classList.add('dark');
toggle.addEventListener('click', () => {{
  body.classList.toggle('dark');
  localStorage.setItem('theme', body.classList.contains('dark') ? 'dark' : 'light');
}});
</script>
</body></html>"""

# ---------- standalone runner ------------------------------------------------

def run(host="127.0.0.1", port=8000):
    app.run(host=host, port=port)

if __name__ == "__main__":
    run()
