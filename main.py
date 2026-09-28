import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
import requests


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Берём только новости, опубликованные за последний час
MAX_AGE_MINUTES = 60

# Файл с уже отправленными новостями
SENT_FILE = "data/sent.json"


# ============================================================
# ПОИСКОВЫЕ ЗАПРОСЫ GOOGLE NEWS
# ============================================================

QUERIES = [

    # ---------------- РУССКИЙ ----------------

    "Казахстан МЧС",
    "Казахстан чрезвычайная ситуация",
    "Казахстан чрезвычайное происшествие",
    "Казахстан пожар спасатели",
    "Казахстан пожар МЧС",
    "Казахстан спасатели",
    "Казахстан спасательная операция",
    "Казахстан эвакуация МЧС",
    "Казахстан наводнение МЧС",
    "Казахстан паводок МЧС",
    "Казахстан подтопление МЧС",
    "Казахстан землетрясение МЧС",
    "Казахстан взрыв МЧС",
    "Казахстан обрушение МЧС",
    "Казахстан авария МЧС",
    "Казахстан стихия МЧС",
    "Казахстан природная ЧС",
    "Казахстан техногенная ЧС",
    "Казахстан поисково-спасательные работы",
    "Казахстан спасли МЧС",
    "Казахстан спасли спасатели",
    "Казахстан МЧС спасли",
    "Казахстан пропал спасатели",
    "Казахстан застряли спасатели",

    # ---------------- ҚАЗАҚША ----------------

    "Қазақстан ТЖМ",
    "Қазақстан төтенше жағдай",
    "Қазақстан төтенше оқиға",
    "Қазақстан өрт құтқарушылар",
    "Қазақстан өрт ТЖМ",
    "Қазақстан құтқарушылар",
    "Қазақстан құтқару операциясы",
    "Қазақстан ТЖМ эвакуация",
    "Қазақстан су тасқыны ТЖМ",
    "Қазақстан су басу ТЖМ",
    "Қазақстан су жайылуы ТЖМ",
    "Қазақстан жер сілкінісі ТЖМ",
    "Қазақстан жарылыс ТЖМ",
    "Қазақстан ғимарат құлауы ТЖМ",
    "Қазақстан апат ТЖМ",
    "Қазақстан табиғи апат",
    "Қазақстан техногендік апат",
    "Қазақстан іздестіру құтқару жұмыстары",
    "Қазақстан құтқарушылар құтқарды",
    "Қазақстан ТЖМ құтқарды",
    "Қазақстан жоғалып кетті құтқарушылар",
    "Қазақстан құтқарушылар іздеді",
]


# ============================================================
# ЧЁРНЫЙ СПИСОК
# ============================================================

# Если в новости есть эти слова, она будет отсеяна,
# если одновременно нет сильных признаков ЧС.

EXCLUDE_KEYWORDS = [
    # Обычные ДТП
    "дтп",
    "дорожно-транспортное происшествие",
    "автокөлік апаты",

    # Криминал
    "убийство",
    "убил",
    "убита",
    "убит",
    "наркотик",
    "наркоторгов",
    "грабеж",
    "ограбление",
    "кража",
    "воровство",
    "мошенничество",
    "взятка",
    "коррупция",

    # Суды
    "суд признал",
    "суд приговорил",
    "приговор",
    "задержан",
    "задержали",

    # Спорт
    "футбол",
    "хоккей",
    "баскетбол",
    "теннис",
    "спорт",
    "матч",
    "чемпионат",

    # Политика / экономика
    "выборы",
    "депутат",
    "парламент",
    "сенат",
    "мажилис",
    "президент",
    "министр финансов",
    "курс тенге",
    "инфляция",
    "акции",
]


# Сильные слова ЧС.
# Если они присутствуют, новость считается потенциально
# релевантной даже при наличии некоторых слов из чёрного списка.

EMERGENCY_KEYWORDS = [

    # МЧС
    "мчс",
    "тжм",
    "чс",
    "төтенше жағдай",
    "төтенше оқиға",

    # Пожар
    "пожар",
    "пожары",
    "горел",
    "загорел",
    "возгорание",
    "огонь",
    "өрт",
    "өртенді",
    "өртеніп",

    # Спасатели
    "спасатель",
    "спасатели",
    "спасательную",
    "спасательная",
    "құтқарушы",
    "құтқарушылар",
    "құтқару",

    # Природные ЧС
    "наводнение",
    "наводнения",
    "паводок",
    "паводки",
    "подтопление",
    "подтопило",
    "затопление",
    "сел",
    "сели",
    "оползень",
    "лавина",
    "ураган",
    "шторм",
    "буря",
    "сильный ветер",
    "метель",
    "буран",
    "су тасқыны",
    "су басу",
    "сел",
    "қар көшкіні",
    "дауыл",
    "қатты жел",

    # Землетрясение
    "землетрясение",
    "землетрясения",
    "сейсми",
    "жер сілкінісі",

    # Взрывы
    "взрыв",
    "взрыва",
    "взорвался",
    "взорвалось",
    "жарылыс",

    # Обрушения
    "обрушение",
    "обрушился",
    "обрушилось",
    "обвал",
    "здание рухнуло",
    "құлады",
    "құлау",

    # Эвакуация
    "эвакуация",
    "эвакуировали",
    "эвакуирован",
    "эвакуациялау",

    # Спасательные работы
    "спасли",
    "спасено",
    "спасен",
    "спасена",
    "спасение",
    "поисково-спас",
    "поиск людей",
    "пропал",
    "пропавш",
    "застряли",
    "застрял",
    "іздестіру",
    "жоғалып",
    "құтқарды",
]


# ============================================================
# РАБОТА С SENT.JSON
# ============================================================

def load_sent():
    if not os.path.exists(SENT_FILE):
        return set()

    try:
        with open(SENT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            return set()

        return set(data)

    except Exception as e:
        print(f"Ошибка чтения {SENT_FILE}: {e}")
        return set()


def save_sent(sent):
    # Оставляем максимум 2000 последних ссылок
    sent_list = list(sent)[-2000:]

    os.makedirs(os.path.dirname(SENT_FILE), exist_ok=True)

    with open(SENT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            sent_list,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# GOOGLE NEWS
# ============================================================

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
        published = parsedate_to_datetime(value)

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        return published.astimezone(timezone.utc)

    except Exception as e:
        print(f"Не удалось определить дату публикации: {e}")
        return None


def clean_text(text):
    if not text:
        return ""

    # Удаляем HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # Убираем лишние пробелы
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# ПРОВЕРКА РЕЛЕВАНТНОСТИ
# ============================================================

def is_emergency_news(article):
    title = article["title"].lower()
    summary = article["summary"].lower()

    text = f"{title} {summary}"

    # Есть ли признаки ЧС?
    has_emergency_keyword = any(
        keyword.lower() in text
        for keyword in EMERGENCY_KEYWORDS
    )

    if not has_emergency_keyword:
        return False

    # Проверяем исключения
    for keyword in EXCLUDE_KEYWORDS:

        if keyword.lower() in text:

            # Если одновременно есть сильный признак ЧС,
            # оставляем новость.
            strong_emergency = any(
                strong.lower() in text
                for strong in [
                    "мчс",
                    "тжм",
                    "чс",
                    "төтенше жағдай",
                    "спасател",
                    "құтқар",
                    "пожар",
                    "өрт",
                    "наводнение",
                    "паводок",
                    "землетрясение",
                    "жер сілкінісі",
                    "взрыв",
                    "жарылыс",
                    "обрушение",
                    "эвакуация",
                    "су тасқыны",
                ]
            )

            if not strong_emergency:
                return False

    return True


# ============================================================
# ПОЛУЧЕНИЕ НОВОСТЕЙ
# ============================================================

def get_articles():
    articles = []

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(
        minutes=MAX_AGE_MINUTES
    )

    print(
        f"Ищем новости с "
        f"{cutoff.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    print(
        f"до {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    total_found = 0
    old_news = 0
    irrelevant_news = 0

    for query in QUERIES:

        print("")
        print(f"Google News: {query}")

        try:
            url = get_google_news_url(query)

            feed = feedparser.parse(url)

            for entry in feed.entries:

                total_found += 1

                article_url = entry.get(
                    "link",
                    "",
                ).strip()

                if not article_url:
                    continue

                published = get_published_time(entry)

                if not published:
                    continue

                # Старше часа — пропускаем
                if published < cutoff:
                    old_news += 1
                    continue

                # Защита от неправильной даты
                if published > now + timedelta(minutes=10):
                    continue

                title = clean_text(
                    entry.get(
                        "title",
                        "Без названия",
                    )
                )

                summary = clean_text(
                    entry.get(
                        "summary",
                        "",
                    )
                )

                source = ""

                if entry.get("source"):
                    try:
                        source = entry.source.get(
                            "title",
                            "",
                        )
                    except Exception:
                        source = ""

                article = {
                    "title": title,
                    "url": article_url,
                    "published": published,
                    "summary": summary,
                    "source": source,
                }

                # Проверяем релевантность
                if not is_emergency_news(article):
                    irrelevant_news += 1
                    continue

                articles.append(article)

        except Exception as e:
            print(
                f"Ошибка Google News "
                f"для '{query}': {e}"
            )

    print("")
    print("========== СТАТИСТИКА ==========")
    print(f"Всего результатов Google News: {total_found}")
    print(f"Старше 60 минут: {old_news}")
    print(f"Отфильтровано как нерелевантные: {irrelevant_news}")
    print(f"Релевантных новостей: {len(articles)}")
    print("================================")

    return articles


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(article):

    title = html.escape(
        clean_text(article["title"])
    )

    source = html.escape(
        clean_text(article["source"])
    )

    url = article["url"]

    message = f"<b>{title}</b>"

    if source:
        message += (
            f"\n\nИсточник: {source}"
        )

    message += (
        f'\n\n<a href="{html.escape(url, quote=True)}">'
        f"Открыть новость"
        f"</a>"
    )

    telegram_url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        telegram_url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    if not response.ok:
        print(
            f"Telegram ответил: "
            f"{response.status_code}"
        )

        print(response.text)

    response.raise_for_status()


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():

    print("")
    print("================================")
    print("   MChS Kazakhstan News Monitor")
    print("================================")
    print("")

    sent = load_sent()

    articles = get_articles()

    # Убираем дубли по URL
    unique_articles = {}

    for article in articles:

        url = article["url"]

        if url not in unique_articles:
            unique_articles[url] = article

    articles = list(
        unique_articles.values()
    )

    # Самые свежие сначала
    articles.sort(
        key=lambda article: article["published"],
        reverse=True,
    )

    print("")
    print(
        f"После удаления дублей: "
        f"{len(articles)}"
    )

    new_count = 0
    duplicate_count = 0

    for article in articles:

        url = article["url"]

        if url in sent:

            duplicate_count += 1

            print(
                f"Уже отправляли: "
                f"{article['title']}"
            )

            continue

        try:

            send_telegram(article)

            sent.add(url)

            new_count += 1

            published_local = (
                article["published"]
                .astimezone()
                .strftime(
                    "%H:%M"
                )
            )

            print("")
            print(
                f"ОТПРАВЛЕНО [{published_local}]: "
                f"{article['title']}"
            )

        except Exception as e:

            print(
                f"Ошибка отправки в Telegram: "
                f"{e}"
            )

    save_sent(sent)

    print("")
    print("========== ИТОГ ==========")
    print(
        f"Новых отправленных новостей: "
        f"{new_count}"
    )

    print(
        f"Уже были отправлены: "
        f"{duplicate_count}"
    )

    print("==========================")
    print("")


if __name__ == "__main__":
    main()
