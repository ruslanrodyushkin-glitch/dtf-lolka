"""
Пересылает новости DTF (RSS) в канал Lolka через вебхук.

Установка:  pip install feedparser requests
Запуск:     LOLKA_WEBHOOK_URL="https://lolka.app/api/webhooks/ID/TOKEN" python dtf_to_lolka.py

Запускайте раз в 5–10 минут (cron / Планировщик заданий Windows).
При первом запуске бот только запоминает текущие новости и ничего не постит,
чтобы не заспамить канал старыми записями.
"""
import json
import os
import sys
import time
from pathlib import Path

import feedparser
import requests

FEED_URL = "https://dtf.ru/rss"
WEBHOOK_URL = os.environ.get("LOLKA_WEBHOOK_URL")
SEEN_FILE = Path(__file__).with_name("dtf_seen.json")

if not WEBHOOK_URL:
    sys.exit("Задайте переменную окружения LOLKA_WEBHOOK_URL")

first_run = not SEEN_FILE.exists()
seen = set() if first_run else set(json.loads(SEEN_FILE.read_text("utf-8")))

feed = feedparser.parse(FEED_URL)
if feed.bozo and not feed.entries:
    sys.exit(f"Не удалось прочитать ленту: {feed.bozo_exception}")

# старые сверху, новые снизу
for entry in reversed(feed.entries):
    guid = entry.get("id") or entry.get("link")
    if guid in seen:
        continue
    seen.add(guid)
    if first_run:
        continue

    link = entry.link.replace("?from=rss", "")
    image = next((e.href for e in entry.get("enclosures", [])
                  if e.get("type", "").startswith("image")), None)
    summary = (entry.get("summary") or "").split("<")[0].strip()

    payload = {
        "username": "DTF",
        "content": f"**{entry.title}**\n{summary}\n{link}",
    }
    if image:  # Lolka совместима с форматом Discord; если embeds не отобразятся — удалите этот блок
        payload["embeds"] = [{"image": {"url": image}}]

    r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", 5)))
        r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    r.raise_for_status()
    time.sleep(1)

SEEN_FILE.write_text(json.dumps(sorted(seen)[-500:]), "utf-8")
print("Первый запуск: новости запомнены" if first_run else "Готово")
