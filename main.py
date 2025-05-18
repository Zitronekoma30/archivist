import json, threading
import bot, web

# ----- config & token ----------------------
with open('config.json') as f:
    cfg = json.load(f)

with open('token') as f:
    TOKEN = f.read().strip()
# -------------------------------------------

# run Flask in a background thread
threading.Thread(
    target=web.run,
    kwargs={'host': cfg['flask_host'], 'port': cfg['flask_port']},
    daemon=True
).start()

# run Discord bot (blocks)
bot.run(TOKEN, cfg['domain'])
