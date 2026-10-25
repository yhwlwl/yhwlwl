#!/usr/bin/env python3
"""Render a self-hosted contribution activity SVG from GitHub's GraphQL API.

Requires GH_TOKEN (the repository's existing METRICS_TOKEN secret).
Never fills missing days with invented activity.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

LOGIN = "yhwlwl"
OUTPUT = Path("activity-graph.svg")
DAYS = 31
GRAPHQL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def get_activity():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN / METRICS_TOKEN must be configured in repository Secrets")
    now = datetime.now(timezone.utc)
    first = (now - timedelta(days=DAYS - 1)).date()
    variables = {
        "login": LOGIN,
        "from": first.isoformat() + "T00:00:00Z",
        "to": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    req = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GRAPHQL_QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "yhwlwl-profile-activity",
        },
        method="POST",
    )
    with urlopen(req, timeout=40) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL failed: " + json.dumps(payload["errors"]))
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError("GitHub GraphQL returned no user: " + LOGIN)
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    count_by_day = {
        item["date"]: int(item["contributionCount"])
        for week in weeks for item in week["contributionDays"]
    }
    dates = [first + timedelta(days=i) for i in range(DAYS)]
    if any(date.isoformat() not in count_by_day for date in dates):
        raise RuntimeError("Incomplete daily contribution history; refusing to invent points")
    return [(date.isoformat(), count_by_day[date.isoformat()]) for date in dates]


def draw(points):
    width, height = 960, 285
    left, right, top, bottom = 58, 928, 94, 224
    maximum = max(1, max(value for _, value in points))
    total = sum(value for _, value in points)
    xy = [
        (left + i * (right - left) / (len(points) - 1),
         bottom - (value / maximum) * (bottom - top))
        for i, (_, value) in enumerate(points)
    ]
    path = " ".join(
        ("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}"
        for i, (x, y) in enumerate(xy)
    )
    area = path + f" L{right},{bottom} L{left},{bottom} Z"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="285" viewBox="0 0 960 285" role="img" aria-label="yhwlwl daily GitHub contributions over the last 31 days">',
        '<rect x="1" y="1" width="958" height="283" rx="12" fill="#ffffff" stroke="#d0d7de" stroke-width="2"/>',
        '<text x="28" y="37" fill="#0969da" font-family="Arial,Helvetica,sans-serif" font-size="20" font-weight="bold">Recent GitHub Activity</text>',
        f'<text x="932" y="37" text-anchor="end" fill="#57606a" font-family="Arial,Helvetica,sans-serif" font-size="15">{total:,} contributions in 31 days</text>',
    ]
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        y = bottom - fraction * (bottom - top)
        value = round(maximum * fraction)
        parts.append(f'<path d="M{left},{y:.1f}H{right}" stroke="#eaeef2" stroke-width="1"/>')
        parts.append(f'<text x="46" y="{y + 5:.1f}" text-anchor="end" font-family="Arial,Helvetica,sans-serif" font-size="11" fill="#6e7781">{value}</text>')
    parts.append(f'<path d="{area}" fill="#dbeafe" fill-opacity="0.78"/>')
    parts.append(f'<path d="{path}" fill="none" stroke="#0969da" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    for x, y in xy:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#1f6feb" stroke="#ffffff" stroke-width="1.2"/>')
    for i in (0, 5, 10, 15, 20, 25, 30):
        x = xy[i][0]
        date = datetime.strptime(points[i][0], "%Y-%m-%d")
        label = escape(date.strftime("%b %d"))
        anchor = "start" if i == 0 else ("end" if i == 30 else "middle")
        parts.append(f'<text x="{x:.1f}" y="252" text-anchor="{anchor}" fill="#57606a" font-family="Arial,Helvetica,sans-serif" font-size="12">{label}</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    history = get_activity()
    OUTPUT.write_text(draw(history), encoding="utf-8")
    print(f"Rendered {OUTPUT}: {len(history)} real dates, {sum(n for _, n in history)} contributions")
