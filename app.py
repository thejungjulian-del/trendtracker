"""
app.py — the web dashboard.

Run it with:   python3 app.py
Then open:     http://127.0.0.1:5005  in your browser.

It shows:
  • Trending TikTok hashtags (auto-pulled, free)
  • Trends YOU logged (Instagram or anything you spotted)
  • A "rising" panel showing what's climbing vs the last snapshot
A button refreshes TikTok; a form lets you log your own trend.
"""

import os

from flask import Flask, render_template, request, redirect, url_for, flash

import db
import collector

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(16).hex()  # only signs flash messages

# Make sure the database + table exist before the first request.
db.init_db()


@app.route("/")
def home():
    return render_template(
        "dashboard.html",
        stats=db.stats(),
        google=db.latest_per_source("google", limit=40),
        tiktok=db.latest_per_source("tiktok", limit=40),
        fashion=db.fashion_highlights(limit=25),
        logged=db.recent_manual(limit=40),
        rising=db.rising("google", limit=10),
    )


@app.route("/refresh", methods=["POST"])
def refresh():
    """The 'Refresh TikTok' button calls this."""
    total, msg = collector.run_collection()
    flash(msg, "ok" if total else "warn")
    return redirect(url_for("home"))


@app.route("/log", methods=["POST"])
def log():
    """The manual 'log a trend' form calls this."""
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Please type a trend name.", "warn")
        return redirect(url_for("home"))
    db.add_trend(
        source=request.form.get("source") or "manual",
        category=request.form.get("category") or "other",
        name=name,
        detail=(request.form.get("detail") or "").strip() or None,
        url=(request.form.get("url") or "").strip() or None,
    )
    flash(f"Logged: {name}", "ok")
    return redirect(url_for("home"))


if __name__ == "__main__":
    # debug=True auto-reloads when you edit the code. port 5005 avoids clashing
    # with other local apps.
    app.run(host="127.0.0.1", port=5005, debug=True)
