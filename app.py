from flask import Flask, request, redirect, render_template_string
import os, string, random, psycopg2
from psycopg2.extras import RealDictCursor
import redis
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ------------------------------
# DATABASE & REDIS
# ------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
REDIS_URL = os.environ.get("REDIS_URL")

r = redis.from_url(REDIS_URL)

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id BIGSERIAL PRIMARY KEY,
                long_url TEXT NOT NULL,
                short_code VARCHAR(12) UNIQUE NOT NULL,
                clicks BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_short_code ON urls(short_code);
            """)
            conn.commit()

# ------------------------------
# SHORT CODE GENERATION
# ------------------------------
def generate_short_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def create_unique_short_code(long_url, custom_code=None):
    attempt = 0
    code = custom_code if custom_code else generate_short_code()
    while attempt < 10:
        if not r.exists(code):
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO urls (long_url, short_code) VALUES (%s, %s) ON CONFLICT (short_code) DO NOTHING RETURNING short_code;",
                            (long_url, code)
                        )
                        row = cur.fetchone()
                        if row:
                            r.set(code, long_url)
                            return row[0]
            except Exception:
                pass
        code = generate_short_code()
        attempt += 1
    raise Exception("Cannot generate unique short code. Try again later.")

# ------------------------------
# ROUTES
# ------------------------------
@app.route("/", methods=["GET","POST"])
def index():
    short_url = None
    error = None
    if request.method=="POST":
        long_url=request.form["long_url"]
        custom_code=request.form.get("custom_code")
        try:
            short_code=create_unique_short_code(long_url,custom_code)
            short_url=request.host_url+short_code
        except Exception as e:
            error=str(e)
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT short_code, clicks, long_url FROM urls ORDER BY id DESC LIMIT 10")
            history = cur.fetchall()
    return render_template_string("""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>URL Shortener</title></head>
<body>
<h1>URL Shortener</h1>
<form method="post">
<input type="url" name="long_url" placeholder="Long URL" required>
<input type="text" name="custom_code" placeholder="Custom code (optional)">
<button type="submit">Shorten</button>
</form>
{% if short_url %}<div><a href="{{ short_url }}" target="_blank">{{ short_url }}</a></div>{% endif %}
{% if history %}
<table>
<tr><th>Short</th><th>Clicks</th><th>Long URL</th></tr>
{% for h in history %}
<tr>
<td><a href="/{{ h.short_code }}">{{ h.short_code }}</a></td>
<td>{{ h.clicks }}</td>
<td>{{ h.long_url }}</td>
</tr>
{% endfor %}
</table>
{% endif %}
</body>
</html>
""", short_url=short_url, history=history, error=error)

@app.route("/<short_code>")
def redirect_url(short_code):
    long_url=r.get(short_code)
    if long_url:
        r.incr(f"clicks:{short_code}")
        return redirect(long_url.decode())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT long_url FROM urls WHERE short_code=%s",(short_code,))
            row=cur.fetchone()
            if row:
                long_url_db=row[0]
                r.set(short_code,long_url_db)
                r.incr(f"clicks:{short_code}")
                return redirect(long_url_db)
    return "URL not found",404

# ------------------------------
# BACKGROUND TASK: Sync Clicks
# ------------------------------
def sync_clicks():
    with get_db() as conn:
        with conn.cursor() as cur:
            for key in r.scan_iter("clicks:*"):
                short_code=key.decode().split(":")[1]
                clicks=int(r.get(key))
                cur.execute("UPDATE urls SET clicks=clicks+%s WHERE short_code=%s",(clicks,short_code))
                r.delete(key)
        conn.commit()

scheduler=BackgroundScheduler()
scheduler.add_job(func=sync_clicks,trigger="interval",seconds=60)
scheduler.start()

# ------------------------------
# START
# ------------------------------
if __name__=="__main__":
    init_db()
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
