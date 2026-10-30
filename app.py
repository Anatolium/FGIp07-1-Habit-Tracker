"""Habit Tracker - personal habit coach.

Single-file Flask backend: SQLite storage, JSON API for a small vanilla-JS UI.
"""

import os
import random
import re
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, g, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("HABIT_DB", os.path.join(BASE_DIR, "habits.db"))

# Key habit milestones (days of a continuous streak).
MILESTONES = (7, 21, 40)
HISTORY_DAYS = 30
DEFAULT_HABIT = "Зарядка по утрам"

SUCCESS_MESSAGES = [
    "Отлично! Ещё один день в вашу пользу.",
    "Так держать! Серия растёт.",
    "Вы сделали это. Маленький шаг — большая привычка.",
    "Ещё одна победа. Вы сильнее, чем вчера.",
    "Здорово! Сегодня вы на своей стороне.",
    "Отличная работа. Привычка крепнет с каждым днём.",
    "Супер! Именно так и строятся большие перемены.",
]

MISS_MESSAGES = [
    "Сегодня не получилось — и это нормально. Завтра новый день.",
    "Пропуск — не провал. Главное, что вы продолжаете.",
    "Всё в порядке. Отдохните и возвращайтесь завтра.",
    "Один день ничего не решает. Продолжаем без чувства вины.",
    "Бывает. Важно не идеальное, а постоянное.",
    "Не ругайте себя: путь к привычке не бывает ровным.",
]

MILESTONE_MESSAGES = {
    7: "Поздравляем! 7 дней подряд — первая серьёзная ступень. Так держать!",
    21: "Поздравляем! 21 день подряд — привычка уже формируется!",
    40: "Поздравляем! 40 дней подряд — это настоящий результат!",
}

app = Flask(__name__, static_url_path="/tracker-1/static")


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                day        TEXT PRIMARY KEY,
                done       INTEGER NOT NULL,
                message    TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def load_entries():
    rows = get_db().execute("SELECT day, done FROM entries").fetchall()
    return {row["day"]: bool(row["done"]) for row in rows}


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def iso(d):
    return d.isoformat()


def best_streak(entries):
    """Length of the longest run of consecutive successful days."""
    best = 0
    current = 0
    previous = None
    for day in sorted(entries):
        if entries[day]:
            if previous is not None and (date.fromisoformat(day) - date.fromisoformat(previous)).days == 1:
                current += 1
            else:
                current = 1
        else:
            current = 0
        previous = day
        best = max(best, current)
    return best


def current_streak(entries, today=None):
    """Consecutive successful days up to today (today may still be unanswered)."""
    today = today or date.today()
    day = today
    if iso(today) not in entries:
        day = today - timedelta(days=1)
    streak = 0
    while entries.get(iso(day)) is True:
        streak += 1
        day -= timedelta(days=1)
    return streak


def build_stats(entries, today=None):
    today = today or date.today()
    return {
        "current_streak": current_streak(entries, today),
        "best_streak": best_streak(entries),
        "total_wins": sum(1 for value in entries.values() if value),
        "total_answers": len(entries),
    }


def build_achievements(stats):
    best = stats["best_streak"]
    return [{"days": days, "unlocked": best >= days} for days in MILESTONES]


def build_history(entries, today=None, days=HISTORY_DAYS):
    today = today or date.today()
    items = []
    for offset in range(days):
        day = today - timedelta(days=offset)
        key = iso(day)
        if key not in entries:
            status = "none"
        else:
            status = "done" if entries[key] else "miss"
        items.append({"day": key, "status": status})
    return items


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def habit_name():
    return get_setting("habit", DEFAULT_HABIT)


def reminder_time():
    return get_setting("reminder_time", "")


def pick_message(done, unlocked_milestones):
    if done and unlocked_milestones:
        return MILESTONE_MESSAGES[max(unlocked_milestones)]
    return random.choice(SUCCESS_MESSAGES if done else MISS_MESSAGES)


def state_payload(entries=None, extra=None):
    entries = load_entries() if entries is None else entries
    stats = build_stats(entries)
    payload = {
        "habit": habit_name(),
        "reminder_time": reminder_time(),
        "today": iso(date.today()),
        "today_done": entries.get(iso(date.today())),
        "today_message": None,
        "stats": stats,
        "achievements": build_achievements(stats),
        "history": build_history(entries),
    }
    row = get_db().execute(
        "SELECT message FROM entries WHERE day = ?", (iso(date.today()),)
    ).fetchone()
    if row:
        payload["today_message"] = row["message"]
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return jsonify(state_payload())


@app.post("/api/answer")
def api_answer():
    data = request.get_json(silent=True) or {}
    done = data.get("done")
    if not isinstance(done, bool):
        return jsonify({"error": "Поле 'done' должно быть true или false."}), 400

    day = iso(date.today())
    entries = load_entries()
    before_best = best_streak(entries)

    db = get_db()
    db.execute(
        "INSERT INTO entries (day, done, message, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(day) DO UPDATE SET done = excluded.done, updated_at = excluded.updated_at",
        (day, int(done), "", datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()

    entries = load_entries()
    after_best = best_streak(entries)
    new_achievements = [d for d in MILESTONES if before_best < d <= after_best]
    reached_now = [d for d in MILESTONES if d == current_streak(entries)] if done else []
    reached = sorted(set(new_achievements) | set(reached_now))
    message = pick_message(done, reached)

    db.execute("UPDATE entries SET message = ? WHERE day = ?", (message, day))
    db.commit()

    return jsonify(state_payload(entries, {"message": message, "new_achievements": new_achievements}))


@app.post("/api/habit")
def api_habit():
    data = request.get_json(silent=True) or {}
    habit = (data.get("habit") or "").strip()
    if not habit:
        return jsonify({"error": "Название привычки не может быть пустым."}), 400
    if len(habit) > 120:
        return jsonify({"error": "Слишком длинное название (максимум 120 символов)."}), 400

    set_setting("habit", habit)
    return jsonify(state_payload())


@app.post("/api/reminder")
def api_reminder():
    data = request.get_json(silent=True) or {}
    value = (data.get("reminder_time") or "").strip()
    if value and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        return jsonify({"error": "Время должно быть в формате ЧЧ:ММ (например, 20:30)."}), 400

    set_setting("reminder_time", value)
    return jsonify(state_payload())


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Страница не найдена."}), 404


@app.errorhandler(Exception)
def server_error(error):
    if isinstance(error, sqlite3.Error):
        app.logger.exception("Database error")
        return jsonify({"error": "Ошибка базы данных. Попробуйте ещё раз."}), 500
    app.logger.exception("Unexpected error")
    return jsonify({"error": "Внутренняя ошибка сервера."}), 500


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
