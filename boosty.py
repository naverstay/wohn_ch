import os
import requests
import argparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import zoneinfo

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT = os.getenv("TG_CHAT")

parser = argparse.ArgumentParser()
parser.add_argument("--interval", type=int, default=6)
args = parser.parse_args()

interval_hours = args.interval

CHANNELS = [
    "historipi",
    "prosvet-b",
    "ot_adama_do_potsdama"
]

URL = "https://boosty.to/"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

def send_telegram(message: str, token: str, chat_id: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    requests.post(url, data=data)


def get_tz(name):
    try:
        return zoneinfo.ZoneInfo(name)
    except:
        return zoneinfo.ZoneInfo("UTC")

def parse_boosty_date(raw: str) -> datetime:
    parts = raw.split()
    month = MONTHS[parts[0]]
    day = int(parts[1])
    hour, minute = map(int, parts[2].split(":"))

    year = datetime.now().year

    # Boosty → UTC
    dt = datetime(year, month, day, hour, minute, tzinfo=zoneinfo.ZoneInfo("UTC"))

    # Конвертация в локальное время
    return dt.astimezone(get_tz("Europe/Berlin"))


def get_last_post_info(channel):
    r = requests.get(URL + channel, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

#     with open("page.html", "w", encoding="utf-8") as f:
#         f.write(r.text)
#
#     print("HTML сохранён в page.html")

    # Дата
    date_selector = 'article div[data-post-id] .BasePostHeader-scss--module_headerLeftBlock_njYUq a'
    date_tag = soup.select_one(date_selector)

    # Заголовок
    title_selector = 'article div[data-post-id] article .PostSubscriptionBlockBase-scss--module_title_Akfk7'
    title_tag = soup.select_one(title_selector)

    # --- Парсим дату ---
    if date_tag:
        raw_date = date_tag.text.strip()  # например: "Feb 15 00:03"
        try:
            dt_local = parse_boosty_date(raw_date)
            iso_date = dt_local.isoformat()
        except Exception:
            iso_date = raw_date
    else:
        iso_date = "Дата не найдена"

    title = title_tag.text.strip() if title_tag else "Заголовок не найден"

    return iso_date, raw_date, title


# --- Основной код ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=6)
    parser.add_argument("--tg_token", type=str, default=TG_TOKEN)
    parser.add_argument("--tg_chat", type=str, default=TG_CHAT)
    args = parser.parse_args()

    interval_hours = args.interval
    local_tz = get_tz("Europe/Berlin")
    now = datetime.now(local_tz)
    previous_run = now - timedelta(hours=interval_hours)

    for channel in CHANNELS:
        iso_date, raw_date, title = get_last_post_info(channel)

        if not iso_date:
            print(f"[{channel}] Не удалось получить данные")
            continue

        post_dt = datetime.fromisoformat(iso_date)

        print(f"[{channel}] {raw_date}: {title}")

        if post_dt > previous_run:
            msg = f"[{channel}] {raw_date}: {title}"
            send_telegram(msg, args.tg_token, args.tg_chat)
            print("→ Отправлено уведомление в Telegram")
        else:
            print("→ Новых постов нет")
