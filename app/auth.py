"""Accounts: email + password (PBKDF2), cookie sessions, saved quiz profile. SQLite only."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from app.db import connect

ITERATIONS = 200_000
SESSION_COOKIE = "playpath_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    pw_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""


class AuthError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def init_auth() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _new_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token, user_id, _now()))
    return token


def signup(email: str, password: str, name: str = "") -> tuple[dict[str, Any], str]:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    salt = secrets.token_hex(16)
    conn = connect()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise AuthError("An account with that email already exists.")
        cur = conn.execute(
            "INSERT INTO users (email, name, pw_hash, salt, created) VALUES (?,?,?,?,?)",
            (email, name.strip()[:80], _hash(password, salt), salt, _now()),
        )
        token = _new_session(conn, cur.lastrowid)
        conn.commit()
        return {"id": cur.lastrowid, "email": email, "name": name.strip()[:80]}, token
    finally:
        conn.close()


def login(email: str, password: str) -> tuple[dict[str, Any], str]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        # Same message either way so the form doesn't reveal which emails exist.
        if row is None or not hmac.compare_digest(_hash(password, row["salt"]), row["pw_hash"]):
            raise AuthError("Email or password is incorrect.")
        token = _new_session(conn, row["id"])
        conn.commit()
        return {"id": row["id"], "email": row["email"], "name": row["name"]}, token
    finally:
        conn.close()


def logout(token: str | None) -> None:
    if not token:
        return
    conn = connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()


def user_for(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    conn = connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token=?",
            (token,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_profile(user_id: int) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        return json.loads(row["data"]) if row else None
    finally:
        conn.close()


def save_profile(user_id: int, data: dict[str, Any]) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO profiles VALUES (?, ?, ?)", (user_id, json.dumps(data), _now())
        )
        conn.commit()
    finally:
        conn.close()


def update_account(user_id: int, name: str | None) -> None:
    conn = connect()
    try:
        if name is not None:
            conn.execute("UPDATE users SET name=? WHERE id=?", (name.strip()[:80], user_id))
        conn.commit()
    finally:
        conn.close()


def delete_account(user_id: int) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
    finally:
        conn.close()
