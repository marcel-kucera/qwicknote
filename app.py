from dataclasses import dataclass
from datetime import datetime
import re
import sqlite3
import os
from flask import Flask, Response, redirect, render_template, request
from markupsafe import escape

from flask import g

DATABASE = "db"
USERNAME = os.environ.get("QWICKNOTE_USERNAME") or "marcel"
PASSWORD = os.environ.get("QWICKNOTE_PASSWORD") or "dong"


def init_db():
    conn = sqlite3.connect("db")
    cur = conn.cursor()
    _ = cur.execute(
        """
    CREATE TABLE IF NOT EXISTS entry (
        id INTEGER PRIMARY KEY,
        inserted INTEGER,
        content TEXT
    );
    """
    )
    conn.commit()
    conn.close()


init_db()


@dataclass
class Entry:
    id: int
    inserted: datetime
    content: str


app = Flask(__name__)


def get_db() -> sqlite3.Connection:
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


def aslink(s: re.Match[str]):
    link = s.group(0)
    return f"<a href='{link}' target='_blank' rel='noopener noreferrer'>{link}</a>"


@app.before_request
def ensure_login():
    if request.path.startswith("/static"):
        return

    unauth_resp = Response(
        "unauthorized", 401, {"WWW-Authenticate": "Basic realm=qwicknote"}
    )

    if request.authorization is None or request.authorization.type != "basic":
        return unauth_resp

    auth = request.authorization.parameters
    username = auth["username"]
    password = auth["password"]
    if username != USERNAME or password != PASSWORD:
        return unauth_resp

    return None


@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor().execute(
        "SELECT id,inserted,content FROM entry ORDER BY inserted DESC"
    )
    res: list[tuple[int, int, str]] = cur.fetchall()
    entries: list[Entry] = []
    for e in res:
        t = datetime.fromtimestamp(e[1])

        content = escape(e[2])
        content = re.sub(r"(https?://[^\s]+)", aslink, content)

        entries.append(Entry(e[0], t, content))

    return render_template("index.html", entries=entries)


@app.route("/add", methods=["POST"])
def add():
    content = request.form["content"]

    conn = get_db()
    _cur = (
        get_db()
        .cursor()
        .execute(
            "INSERT INTO entry (inserted,content) VALUES (unixepoch(),?)", [content]
        )
    )

    conn.commit()

    return redirect("/")


@app.route("/remove", methods=["POST"])
def remove():
    id = request.form["id"]

    conn = get_db()
    _cur = get_db().cursor().execute("DELETE FROM entry WHERE id = ?", [id])
    conn.commit()

    return redirect("/")


@app.teardown_request
def close_connection(_exception: BaseException | None):
    db = getattr(g, "_database", None)
    if db is not None and isinstance(db, sqlite3.Connection):
        db.close()
