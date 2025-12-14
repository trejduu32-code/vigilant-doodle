from flask import Flask, request, redirect, render_template_string
import sqlite3
import string
import random
import os
from datetime import datetime

app = Flask(__name__)
DB_NAME = os.path.join(os.path.dirname(__file__), "urls.db")

# ---------------- DATABASE ----------------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT NOT NULL,
            clicks INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            deleted INTEGER DEFAULT 0
        )
        """)
        conn.commit()

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def is_expired(row):
    if row["expires_at"]:
        return datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.now()
    return False

# ---------------- AUTO CLEANUP ----------------
def cleanup_expired_urls():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            UPDATE urls
            SET deleted = 1
            WHERE expires_at IS NOT NULL
            AND expires_at < CURRENT_TIMESTAMP
            AND deleted = 0
        """)
        conn.commit()

# ---------------- ROUTES ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_expired_urls()  # 🔥 AUTO CLEANUP

    short_url = None
    error = None

    if request.method == "POST":
        long_url = request.form["long_url"]
        custom_code = request.form.get("custom_code")
        expire_date = request.form.get("expire_date")

        short_code = custom_code if custom_code else generate_short_code()
        expires_at = None

        if expire_date:
            expires_at = datetime.strptime(expire_date, "%Y-%m-%d")

        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT * FROM urls WHERE short_code = ?",
                (short_code,)
            ).fetchone()

            # 🔁 RECLAIM LOGIC
            if existing:
                if existing["deleted"] == 1 or is_expired(existing):
                    conn.execute("""
                        UPDATE urls
                        SET long_url=?, clicks=0, expires_at=?, deleted=0, created_at=CURRENT_TIMESTAMP
                        WHERE short_code=?
                    """, (long_url, expires_at, short_code))
                    conn.commit()
                    short_url = request.host_url + short_code
                else:
                    error = "Short code already in use."
            else:
                conn.execute("""
                    INSERT INTO urls (long_url, short_code, expires_at)
                    VALUES (?, ?, ?)
                """, (long_url, short_code, expires_at))
                conn.commit()
                short_url = request.host_url + short_code

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        history = conn.execute("""
            SELECT * FROM urls
            WHERE deleted = 0
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>URL Shortener</title>
<style>
body {
    background:#020617;
    color:#e5e7eb;
    font-family:Arial;
    display:flex;
    justify-content:center;
    padding:40px;
}
.container {
    width:520px;
    background:#0f172a;
    padding:30px;
    border-radius:14px;
}
input, button {
    width:100%;
    padding:10px;
    margin-bottom:10px;
}
button {
    background:#10b981;
    border:none;
    font-weight:bold;
    cursor:pointer;
}
.delete {
    background:#ef4444;
}
table {
    width:100%;
    font-size:0.85rem;
}
td, th {
    padding:6px;
    word-break:break-all;
}
a { color:#22c55e; }
.error { color:#ef4444; }
</style>
</head>

<body>
<div class="container">
<h1>URL Shortener by ExploitZ3r0</h1>

{% if error %}<div class="error">{{ error }}</div>{% endif %}

<form method="post">
<input type="url" name="long_url" placeholder="Long URL" required>
<input type="text" name="custom_code" placeholder="Custom code (optional)">
<label>Expiration date (optional)</label>
<input type="date" name="expire_date">
<button type="submit">Shorten</button>
</form>

{% if short_url %}
<p>Short URL: <a href="{{ short_url }}" target="_blank">{{ short_url }}</a></p>
{% endif %}

<h3>Active URLs</h3>
<table>
<tr>
<th>Code</th><th>Clicks</th><th>Expires</th><th>Action</th>
</tr>
{% for h in history %}
<tr>
<td>{{ h.short_code }}</td>
<td>{{ h.clicks }}</td>
<td>{{ h.expires_at or "Never" }}</td>
<td>
<form method="post" action="/delete/{{ h.short_code }}">
<button class="delete">Delete</button>
</form>
</td>
</tr>
{% endfor %}
</table>

</div>
</body>
</html>
""", short_url=short_url, history=history, error=error)

@app.route("/delete/<short_code>", methods=["POST"])
def delete_url(short_code):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE urls SET deleted=1 WHERE short_code=?",
            (short_code,)
        )
        conn.commit()
    return redirect("/")

@app.route("/<short_code>")
def redirect_url(short_code):
    cleanup_expired_urls()  # 🔥 AUTO CLEANUP

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM urls WHERE short_code=?",
            (short_code,)
        ).fetchone()

        if not row or row["deleted"]:
            return "URL not found", 404

        conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code=?",
            (short_code,)
        )
        conn.commit()
        return redirect(row["long_url"])

# ---------------- START ----------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
