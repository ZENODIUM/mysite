#!/usr/bin/env python3
"""Fetch public GitHub repos + latest YouTube videos into data/portfolio.json."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

GITHUB_USER = "ZENODIUM"
YOUTUBE_CHANNEL_ID = "UC9lhJNC_J3dNxSwMXkPoguw"
MAX_REPOS = 12
MAX_VIDEOS = 8

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "data" / "portfolio.json"
OUTPUT_JS = ROOT / "data" / "portfolio.js"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
YT_NS = {"yt": "http://www.youtube.com/xml/schemas/2015"}


def fetch_json(url: str) -> list | dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "portfolio-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def get_repos() -> list[dict]:
    url = (
        f"https://api.github.com/users/{GITHUB_USER}/repos"
        f"?sort=updated&per_page=100&type=owner"
    )
    repos = fetch_json(url)
    items = []
    for repo in repos:
        if repo.get("fork") or repo.get("archived") or repo.get("private"):
            continue
        name = repo["name"]
        items.append(
            {
                "name": name,
                "description": (repo.get("description") or "").strip(),
                "url": repo["html_url"],
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "updated_at": repo.get("updated_at"),
                "image": f"https://opengraph.githubassets.com/1/{GITHUB_USER}/{name}",
            }
        )
        if len(items) >= MAX_REPOS:
            break
    return items


def get_videos() -> list[dict]:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={YOUTUBE_CHANNEL_ID}"
    )
    xml_text = fetch_text(feed_url)
    root = ET.fromstring(xml_text)
    items = []
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id_el = entry.find("yt:videoId", YT_NS)
        title_el = entry.find("atom:title", ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        published_el = entry.find("atom:published", ATOM_NS)
        if video_id_el is None or title_el is None:
            continue
        video_id = video_id_el.text
        items.append(
            {
                "title": (title_el.text or "").strip(),
                "url": link_el.get("href")
                if link_el is not None
                else f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "published": published_el.text if published_el is not None else None,
                "image": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            }
        )
        if len(items) >= MAX_VIDEOS:
            break
    return items


def main() -> None:
    repos = get_repos()
    videos = get_videos()
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "github_user": GITHUB_USER,
        "youtube_channel": "https://www.youtube.com/@artificialintelligencedotdaily",
        "repos": repos,
        "videos": videos,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, indent=2) + "\n"
    OUTPUT_JSON.write_text(json_text, encoding="utf-8")
    # JS module works when opening index.html via file:// (fetch is blocked there)
    OUTPUT_JS.write_text(
        "window.__PORTFOLIO_DATA__ = " + json.dumps(payload) + ";\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUTPUT_JSON} and {OUTPUT_JS} "
        f"({len(repos)} repos, {len(videos)} videos)"
    )


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc
