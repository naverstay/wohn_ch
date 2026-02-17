import os
import re
import json
import requests
import argparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import zoneinfo

# --- Загрузка .env ---
load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT = os.getenv("TG_CHAT")

# --- Настройки ---
URL = "https://boosty.to/"
CHANNELS = [
    "historipi",
    "prosvet-b",
    "ot_adama_do_potsdama",
]

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

STATE_FILE = "last_sent.json"

def human_date(iso_date: str) -> str:
    dt = datetime.fromisoformat(iso_date)
    return dt.strftime("%d.%m.%Y %H:%M")


# --- Работа с состоянием ---
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# --- Telegram ---
def send_telegram(message: str, token: str, chat_id: str):
    if not token or not chat_id:
        print("TG_TOKEN или TG_CHAT не заданы, пропускаю отправку в Telegram")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": message}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code != 200:
            print("Ошибка отправки в Telegram:", r.text)
    except Exception as e:
        print("Исключение при отправке в Telegram:", e)


# --- Timezone ---
def get_tz(name):
    try:
        return zoneinfo.ZoneInfo(name)
    except Exception:
        return zoneinfo.ZoneInfo("UTC")


# --- Парсинг даты Boosty ---
def parse_boosty_date(raw: str) -> datetime:
    # Ожидаемый формат: "Feb 15 00:03"
    parts = raw.split()
    if len(parts) < 3:
        raise ValueError(f"Неожиданный формат даты: {raw}")

    month_str, day_str, time_str = parts[0], parts[1], parts[2]
    month = MONTHS.get(month_str)
    if not month:
        raise ValueError(f"Неизвестный месяц: {month_str}")

    day = int(day_str)
    hour, minute = map(int, time_str.split(":"))

    year = datetime.now().year

    # Boosty → считаем, что UTC
    dt_utc = datetime(year, month, day, hour, minute, tzinfo=zoneinfo.ZoneInfo("UTC"))
    return dt_utc.astimezone(get_tz("Europe/Berlin"))


# --- Парсинг одного канала ---
def save_page(channel: str, txt: str):
    with open(channel + ".html", "w", encoding="utf-8") as f:
        f.write(txt)

    print("HTML сохранён в " + channel + ".html")

# --- Парсинг одного канала ---
def get_last_post_info(channel: str):
    url = f"{URL}{channel}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    save_page(channel, r.text)

    soup = BeautifulSoup(r.text, "html.parser")

    # 1. Находим JSON
    script_tag = soup.find("script", {"id": "initial-state"})
    if not script_tag:
        print(f"[{channel}] initial-state не найден")
        return None, None, None, None

    try:
        data = json.loads(script_tag.text)
    except Exception as e:
        print(f"[{channel}] Ошибка JSON: {e}")
        return None, None, None, None

    # 2. Достаём список постов
    try:
        posts = data["posts"]["postsList"]["data"]["posts"]
        if not posts:
            print(f"[{channel}] Постов нет")
            return None, None, None, None
    except KeyError:
        print(f"[{channel}] postsList не найден")
        return None, None, None, None

    # 3. Берём самый свежий пост
    post = posts[0]

    # 4. Достаём данные
    publish_ts = post.get("publishTime")  # UNIX timestamp
    title = post.get("title") or "(без заголовка)"
    post_id = post.get("id")
    blog_url = post["user"]["blogUrl"]

    # 5. Формируем ссылку
    link = f"{URL}/{blog_url}/posts/{post_id}"

    # 6. Конвертируем дату
    dt = datetime.fromtimestamp(publish_ts, tz=zoneinfo.ZoneInfo("UTC"))
    dt_local = dt.astimezone(zoneinfo.ZoneInfo("Europe/Berlin"))
    iso_date = dt_local.isoformat()

    return iso_date, title, link


def get_last_post_info_2(channel: str):
    full_channel_url = URL + channel
    r = requests.get(full_channel_url, timeout=100)
    r.raise_for_status()

#     save_page(channel, r.text)

    soup = BeautifulSoup(r.text, "html.parser")

    # Дата
    date_selector = 'article div[data-post-id] .BasePostHeader-scss--module_headerLeftBlock_njYUq a'
    date_tag = soup.select_one(date_selector)

    # Заголовок
    title_selector = 'article div[data-post-id] article.Post-scss--module_content_92UAn h2'
    title_tag = soup.select_one(title_selector)

    # Ссылка на пост
    link_selector = 'article div[data-post-id] article.Post-scss--module_content_92UAn a.Link-scss--module_block_T-ap9'
    link_tag = soup.select_one(link_selector)

    # Формируем ссылку
    if link_tag:
        href = link_tag.get("href", "").strip()
        if href.startswith("/"):
            href = "https://boosty.to" + href
    else:
        href = full_channel_url

    # Чистим URL от лишних слэшей, не трогая https://
    href = re.sub(r'(?<!:)//+', '/', href)

    # Парсим дату
    if date_tag:
        raw_date = date_tag.text.strip()
        try:
            dt_local = parse_boosty_date(raw_date)
            iso_date = dt_local.isoformat()
        except Exception as e:
            print(f"[{channel}] Не удалось распарсить дату '{raw_date}': {e}")
            iso_date = None
    else:
        raw_date = "Дата не найдена"
        iso_date = None

    title = title_tag.text.strip() if title_tag else "Заголовок не найден"

    return iso_date, raw_date, title, href


# --- Основной код ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=6, help="Интервал в часах между проверками")
    parser.add_argument("--tg_token", type=str, default=TG_TOKEN)
    parser.add_argument("--tg_chat", type=str, default=TG_CHAT)
    args = parser.parse_args()

    interval_hours = args.interval
    local_tz = get_tz("Europe/Berlin")
    now = datetime.now(local_tz)
    previous_run = now - timedelta(hours=interval_hours)

    print("Текущее время:", now.isoformat())
    print("Предыдущий запуск (расчётный):", previous_run.isoformat())

    state = load_state()

    for channel in CHANNELS:
        print(f"\n=== Канал: {channel} ===")
        iso_date, title, href = get_last_post_info(channel)

        post_date = human_date(iso_date)

        if not iso_date:
            print(f"[{channel}] Не удалось получить корректную дату. iso_date='{iso_date}'")
            continue

        try:
            post_dt = datetime.fromisoformat(iso_date)
        except Exception as e:
            print(f"[{channel}] Не удалось преобразовать iso_date '{iso_date}': {e}")
            continue

        last_sent_iso = state.get(channel)
        if last_sent_iso:
            try:
                last_sent_dt = datetime.fromisoformat(last_sent_iso)
            except Exception:
                last_sent_dt = None
        else:
            last_sent_dt = None

        print(f"Пост: {title}")
        print(f"Дата: {post_date}")
        print(f"Ссылка: {href}")

        # Уже отправляли этот или более новый пост
        if last_sent_dt and post_dt <= last_sent_dt:
            print(f"→ Уже отправлен ранее {post_date}: {title}")
            continue

        # Проверяем, новее ли пост предыдущего запуска
        if post_dt > previous_run:
            msg = f"{channel}\n{post_date}\n{title}\n{href}"
            send_telegram(msg, args.tg_token, args.tg_chat)
            print("→ Отправлено уведомление в Telegram", msg)

            # Обновляем состояние
            state[channel] = iso_date
            save_state(state)
        else:
            print("→ Пост старый, уведомление не отправляем")
