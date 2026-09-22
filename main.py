import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests
import feedparser


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MAX_AGE_MINUTES = 60

QUERIES = [
    # Русский
    "Казахстан МЧС",
    "Казахстан чрезвычайная ситуация",
    "Казахстан пожар спасатели",
    "Казахстан пожар МЧС",
    "Казахстан наводнение МЧС",
    "Казахстан паводок МЧС",
    "Казахстан землетрясение МЧС",
    "Казахстан спасатели",
    "Казахстан спасательная операция",
    "Казахстан эвакуация МЧС",
    "Казахстан взрыв МЧС",
    "Казахстан обрушение МЧС",
    "Казахстан авария МЧС",

    # Қазақша
    "Қазақстан ТЖМ",
    "Қазақстан төтенше жағдай",
    "Қазақстан өрт құтқарушылар",
    "Қазақстан өрт ТЖМ",
    "Қазақстан су тасқыны ТЖМ",
    "Қазақстан су басу ТЖМ",
    "Қазақстан жер сілкінісі ТЖМ",
    "Қазақстан құтқарушылар",
    "Қазақстан құтқару операциясы",
    "Қазақстан эвакуация ТЖМ",
    "Қазақстан жарылыс ТЖМ",
    "Қазақстан ғимарат құлауы ТЖМ",
    "Қазақстан апат ТЖМ",
]

SENT_FILE = "data/sent.json"


def load_sent():
    if not os.path.exists(SENT_FILE):
        return set()

    with open(SENT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return set(data)


def save_sent(sent):
    # Оставляем только последние 1000 ссылок,
    # чтобы файл не рос бесконечно.
    sent_list = list(sent)[-1000:]

    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_list, f, ensure_ascii=False, indent=2)


def get_google_news_url(query):
    encoded_query = quote(query)

    return (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}"
        "&hl=ru"
        "&gl=KZ"
        "&ceid=KZ:ru"
    )


def get_published_time(entry):
    value = entry.get("published")

    if not value:
        return None

    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_articles():
    articles = []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=MAX_AGE_MINUTES)

    for query in QUERIES:
        print(f"Проверяем Google News: {query}")

        try:
            feed = feedparser.parse(get_google_news_url(query))

            for entry in feed.entries:
                url = entry.get("link", "").strip()

                if not url:
                    continue

                published = get_published_time(entry)

                if not published:
                    continue

                # Берём только новости не старше 60 минут.
                if published < cutoff:
                    continue

                # Защита от странных будущих дат.
                if published > now + timedelta(minutes=10):
                    continue

                title = clean_text(entry.get("title", "Без названия"))

                summary = clean_text(entry.get("summary", ""))

                source = ""

                if entry.get("source"):
                    source = entry.source.get("title", "")

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "published": published,
                        "summary": summary,
                        "source": source,
                    }
                )

        except Exception as e:
            print(f"Ошибка при запросе '{query}': {e}")

    return articles


def send_telegram(article):
    title = article["title"]
    url = article["url"]
    source = article["source"]

    message = f"<b>{title}</b>\n"

    if source:
        message += f"\nИсточник: {source}"

    message += f"\n\n<a href=\"{url}\">Открыть новость</a>"

    telegram_url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def main():
    print("=== MChS News Monitor ===")

    sent = load_sent()

    articles = get_articles()

    print(f"Найдено свежих новостей: {len(articles)}")

    # Убираем дубли по ссылке.
    unique_articles = {}

    for article in articles:
        unique_articles[article["url"]] = article

    articles = list(unique_articles.values())

    # Сначала самые новые.
    articles.sort(
        key=lambda x: x["published"],
        reverse=True,
    )

    new_count = 0

    for article in articles:
        url = article["url"]

        if url in sent:
            print(f"Уже отправляли: {article['title']}")
            continue

        try:
            send_telegram(article)

            sent.add(url)
            new_count += 1

            print(f"ОТПРАВЛЕНО: {article['title']}")

        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")

    save_sent(sent)

    print(f"Новых отправленных новостей: {new_count}")


if __name__ == "__main__":
    main()
