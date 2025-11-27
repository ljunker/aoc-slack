import os
import json
import time
import datetime as dt
from pathlib import Path

import requests
from dateutil import tz
import schedule

# === Config ===
AOC_YEAR = int(os.getenv("AOC_YEAR", dt.datetime.now().year))
AOC_LEADERBOARD_ID = os.environ["AOC_LEADERBOARD_ID"]
AOC_SESSION = os.environ["AOC_SESSION"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
TIMEZONE = os.getenv("TZ", "Europe/Berlin")

STATE_FILE = Path(os.getenv("STATE_FILE", "/data/aoc_state.json"))
AOC_URL = f"https://adventofcode.com/{AOC_YEAR}/leaderboard/private/view/{AOC_LEADERBOARD_ID}.json"


# === AoC fetching & parsing ===

def fetch_leaderboard():
    headers = {
        "Cookie": f"session={AOC_SESSION}",
        "User-Agent": "aoc-slack-webhook-bot"
    }
    resp = requests.get(AOC_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_star_set(leaderboard_json):
    star_set = set()
    members = leaderboard_json.get("members", {})
    for member_id, member in members.items():
        completion = member.get("completion_day_level", {})
        for day_str, parts in completion.items():
            for part_str, info in parts.items():
                star_set.add((str(member_id), int(day_str), int(part_str)))
    return star_set


def member_name(member):
    name = member.get("name")
    if not name:
        return f"Anonymous #{member['id']}"
    return name


# === State handling ===

def load_previous_star_set():
    if not STATE_FILE.exists():
        return set()
    with STATE_FILE.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {(str(m), int(d), int(p)) for m, d, p in raw}


def save_star_set(star_set):
    as_list = [[m, d, p] for (m, d, p) in sorted(star_set)]
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(as_list, f, indent=2)


# === Slack webhook helper ===

def slack_post(text):
    payload = {"text": text}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if not resp.ok:
            print(f"Slack webhook error: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Slack webhook exception: {e}")


# === Jobs ===

def job_check_new_stars():
    print("[job_check_new_stars] Running...")
    lb = fetch_leaderboard()
    current = extract_star_set(lb)
    previous = load_previous_star_set()

    new_stars = current - previous
    if not new_stars:
        print("No new stars.")
        return

    members = lb.get("members", {})
    member_by_id = {str(m["id"]): m for m in members.values()}

    for member_id, day, part in sorted(new_stars, key=lambda x: (x[1], x[2], x[0])):
        m = member_by_id.get(member_id)
        display_name = member_name(m) if m else f"Member {member_id}"

        part_text = "Part 1" if part == 1 else "Part 2"
        msg = f"{display_name} solved Day {day} {part_text} ⭐"
        print("Announcing:", msg)
        slack_post(msg)

    save_star_set(current)


def job_daily_summary():
    now = dt.datetime.now(tz.gettz(TIMEZONE))
    if now.month != 12:
        print("Not december yet, so no board posted.")
        return
    print("[job_daily_summary] Running...")
    lb = fetch_leaderboard()
    members = list(lb.get("members", {}).values())

    members.sort(key=lambda m: m.get("local_score", 0), reverse=True)

    now = dt.datetime.now(tz.gettz(TIMEZONE))
    header = f"*Advent of Code {AOC_YEAR} – Stand {now.strftime('%Y-%m-%d %H:%M')}*"

    lines = []
    for idx, m in enumerate(members, start=1):
        name = member_name(m)
        stars = m.get("stars", 0)
        score = m.get("local_score", 0)
        lines.append(f"{idx:2}. {name}: {stars}⭐ – {score} pts")

    text = header + "\n\n" + "\n".join(lines)
    print("Posting daily summary")
    slack_post(text)


def main():
    if not STATE_FILE.exists():
        print("Initializing state from current leaderboard so we don't back-announce old stars.")
        lb = fetch_leaderboard()
        current = extract_star_set(lb)
        save_star_set(current)

    schedule.every(15).minutes.do(job_check_new_stars)
    schedule.every().day.at("05:59").do(job_daily_summary)

    print("Scheduler started.")
    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
