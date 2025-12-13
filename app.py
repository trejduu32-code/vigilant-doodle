from flask import Flask, request, redirect, render_template_string
import sqlite3
import string
import random
import os
from datetime import datetime, timedelta

app = Flask(__name__)
DB_NAME = os.path.join(os.path.dirname(__file__), "urls.db")

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
        """)
        conn.commit()

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@app.route("/", methods=["GET", "POST"])
def index():
    short_url = None
    error = None

    if request.method == "POST":
        long_url = request.form["long_url"]
        custom_code = request.form.get("custom_code")
        expire_days = request.form.get("expire_days")

        short_code = custom_code if custom_code else generate_short_code()
        expires_at = None
        if expire_days:
            try:
                days = int(expire_days)
                expires_at = datetime.now() + timedelta(days=days)
            except ValueError:
                error = "Expiration must be a number of days."

        if not error:
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    conn.execute(
                        "INSERT INTO urls (long_url, short_code, expires_at) VALUES (?, ?, ?)",
                        (long_url, short_code, expires_at)
                    )
                short_url = request.host_url + short_code
            except sqlite3.IntegrityError:
                error = "Custom code already exists."

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute(
            "SELECT short_code, long_url, clicks, expires_at FROM urls ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>URL Shortener</title>
<style>
body { font-family: Arial; background:#0a0a0a; color:#fff; text-align:center; padding:50px; }
input { width:300px; padding:10px; margin-bottom:10px; }
button { padding:10px 20px; background:#10b981; border:none; color:#000; cursor:pointer; }
.result { margin-top:20px; color:#10b981; }
table { margin-top:20px; width:100%; color:#fff; }
th, td { padding:6px; text-align:left; word-break:break-all; }
.error { color:#ef4444; margin-bottom:10px; }
</style>
<script>
function copyText(text){ navigator.clipboard.writeText(text); alert("Copied!"); }
</script>
</head>
<body>
<h1>URL Shortener</h1>

{% if error %}<div class="error">{{ error }}</div>{% endif %}

<form method="post">
<input type="url" name="long_url" placeholder="Enter long URL" required><br>
<input type="text" name="custom_code" placeholder="Custom code (optional)"><br>
<input type="number" name="expire_days" placeholder="Expire in days (optional)"><br>
<button type="submit">Shorten</button>
</form>

{% if short_url %}
<div class="result">
<a href="{{ short_url }}" target="_blank">{{ short_url }}</a>
<button onclick="copyText('{{ short_url }}')">Copy</button>
</div>
{% endif %}

{% if history %}
<table>
<tr><th>Short</th><th>Clicks</th><th>Long URL</th><th>Expires At</th></tr>
{% for h in history %}
<tr>
<td><a href="/{{ h['short_code'] }}">{{ h['short_code'] }}</a></td>
<td>{{ h['clicks'] }}</td>
<td>{{ h['long_url'] }}</td>
<td>{{ h['expires_at'] if h['expires_at'] else "Never" }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

</body>
</html>
""", short_url=short_url, history=history, error=error)

@app.route("/<short_code>")
def redirect_url(short_code):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT long_url, clicks, expires_at FROM urls WHERE short_code = ?",
            (short_code,)
        ).fetchone()

        if row:
            if row["expires_at"] and datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now():
                return "URL has expired", 404

            conn.execute(
                "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
                (short_code,)
            )
            conn.commit()
            return redirect(row["long_url"])

    return "URL not found", 404

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
