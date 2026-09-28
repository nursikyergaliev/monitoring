import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
import requests


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


# ============================================================
# НАСТРОЙКИ
# ============================================================

# Берём новости только за последний час
MAX_AGE_MINUTES = 60

# Допускаем небольшую задержку часов источника
FUTURE_TOLERANCE_MINUTES = 10

# Файл с уже отправленными новостями
SENT_FILE = "data/sent.json"

# Максимальное количество ссылок в sent.json
MAX_SENT_ITEMS = 3000


# ============================================================
# РАЗРЕШЁННЫЕ САЙТЫ
# ============================================================

ALLOWED_DOMAINS = {
    "inform.kz",
    "kaztag.kz",
    "baq.kz",
    "inbusiness.kz",
    "elordainfo.kz",
    "zakon.kz",
    "sputnik.kz",
    "newtimes.kz",
    "vlast.kz",
    "kt.kz",
    "tengrinews.kz",
    "informburo.kz",
    "nur.kz",
    "ulysmedia.kz",
    "kursiv.media",
    "bestnews.kz",
    "azattyq-ruhy.kz",
    "liter.kz",
    "time.kz",
    "caravan.kz",
    "khabar.kz",
    "astanatv.kz",
    "24.kz",
    "ktk.kz",
    "almaty.tv",
    "1tv.kz",
}


# ============================================================
# ПОИСКОВЫЕ ЗАПРОСЫ GOOGLE NEWS
# ============================================================

# Здесь специально НЕ делаем десятки узких запросов.
#
# Google News будет искать свежие новости,
# а наша программа потом сама решит,
# относится ли материал к ЧС.

QUERIES = [
    "Казахстан МЧС when:1h",
    "Казахстан ТЖМ when:1h",
    "Казахстан ЧС when:1h",
    "Казахстан спасатели when:1h",
    "Казахстан пожар when:1h",
    "Казахстан происшествие when:1h",
    "Казахстан эвакуация when:1h",
    "Казахстан спасли when:1h",
    "Казахстан пропал спасатели when:1h",
    "Казахстан взрыв when:1h",
    "Казахстан обрушение when:1h",
    "Казахстан наводнение when:1h",
    "Казахстан паводок when:1h",
    "Казахстан подтопление when:1h",
    "Казахстан землетрясение when:1h",
    "Казахстан утонул when:1h",

    # Казахский
    "Қазақстан ТЖМ when:1h",
    "Қазақстан төтенше жағдай when:1h",
    "Қазақстан құтқарушылар when:1h",
    "Қазақстан өрт when:1h",
    "Қазақстан құтқарды when:1h",
    "Қазақстан эвакуация when:1h",
    "Қазақстан су тасқыны when:1h",
    "Қазақстан су басу when:1h",
    "Қазақстан жер сілкінісі when:1h",
    "Қазақстан жарылыс when:1h",
    "Қазақстан құлады when:1h",
]


# ============================================================
# КЛЮЧЕВЫЕ СЛОВА ЧС
# ============================================================

# Очень сильные признаки.
# Если найдено несколько таких слов — вероятность релевантности высокая.

STRONG_EMERGENCY_KEYWORDS = {

    # МЧС
    "мчс": 6,
    "тжм": 6,
    "чс": 5,
    "чрезвычайная ситуация": 6,
    "чрезвычайное происшествие": 5,

    # Казахский
    "төтенше жағдай": 6,
    "төтенше оқиға": 6,

    # Пожары
    "пожар": 6,
    "пожары": 6,
    "возгорание": 5,
    "загорелся": 5,
    "загорелась": 5,
    "загорелось": 5,
    "горел": 5,
    "горела": 5,
    "горели": 5,
    "огонь": 4,

    "өрт": 6,
    "өртенді": 6,
    "өртеніп": 6,

    # Спасатели
    "спасатель": 5,
    "спасатели": 5,
    "спасательная": 5,
    "спасательную": 5,
    "спасательные работы": 6,
    "спасение": 5,
    "спасли": 5,
    "спасен": 5,
    "спасена": 5,
    "спасено": 5,

    "құтқарушы": 5,
    "құтқарушылар": 5,
    "құтқару": 5,
    "құтқарды": 5,

    # Наводнения / паводки
    "наводнение": 6,
    "наводнения": 6,
    "паводок": 6,
    "паводки": 6,
    "подтопление": 6,
    "подтопило": 6,
    "затопление": 5,
    "затопило": 5,

    "су тасқыны": 6,
    "су басу": 6,
    "су жайылуы": 5,

    # Сели / лавины / природные явления
    "сел": 5,
    "сели": 5,
    "оползень": 6,
    "оползни": 6,
    "лавина": 6,
    "лавины": 6,
    "шторм": 5,
    "ураган": 5,
    "буря": 4,
    "сильный ветер": 4,
    "метель": 4,
    "буран": 4,

    "қар көшкіні": 6,
    "дауыл": 5,
    "қатты жел": 5,

    # Землетрясения
    "землетрясение": 7,
    "землетрясения": 7,
    "сейсми": 5,
    "жер сілкінісі": 7,

    # Взрывы
    "взрыв": 7,
    "взрыва": 7,
    "взорвался": 7,
    "взорвалось": 7,
    "взрыв газа": 8,

    "жарылыс": 7,

    # Обрушения
    "обрушение": 7,
    "обрушился": 7,
    "обрушилось": 7,
    "обвал": 6,
    "здание рухнуло": 7,

    "құлады": 6,
    "құлау": 6,

    # Эвакуация
    "эвакуация": 5,
    "эвакуировали": 5,
    "эвакуирован": 5,
    "эвакуированы": 5,
    "эвакуациялау": 5,

    # Пропавшие / поиск
    "пропал": 5,
    "пропала": 5,
    "пропали": 5,
    "пропавший": 5,
    "пропавшая": 5,
    "пропавшие": 5,
    "поиск людей": 6,
    "поисково-спас": 7,

    "жоғалып": 5,
    "іздестіру": 6,

    # Тонущие
    "утонул": 7,
    "утонула": 7,
    "утонули": 7,
    "тонул": 5,
    "тонувшего": 5,

    # Пострадавшие / погибшие
    "пострадал": 4,
    "пострадали": 4,
    "пострадавшие": 4,
    "погиб": 5,
    "погибли": 5,
    "погибшие": 5,

    # Опасные ситуации
    "утечка газа": 7,
    "утечка топлива": 5,
    "отравление газом": 7,
    "угарный газ": 6,
}


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ СЛОВА
# ============================================================

# Эти слова сами по себе слабые,
# но вместе с другими признаками помогают.

WEAK_EMERGENCY_KEYWORDS = {

    "авария": 2,
    "аварийный": 2,
    "происшествие": 2,
    "инцидент": 2,
    "травмирован": 2,
    "травмы": 2,
    "пострадавший": 2,
    "погибший": 3,
    "полиция": 1,
    "дежурная служба": 2,
    "служба спасения": 3,
    "оперативные службы": 3,
    "бригада": 1,
    "экстренные службы": 4,
    "спасательная операция": 5,

    "апат": 3,
    "оқиға": 2,
    "зардап шеккен": 3,
    "қаза тапты": 4,
}


# ============================================================
# ИСКЛЮЧАЮЩИЕ СЛОВА
# ============================================================

# Эти слова НЕ запрещают новость автоматически.
# Они уменьшают её оценку.
#
# Это важно:
# "ДТП + спасатели + пострадавшие"
# должно иметь возможность пройти.

NEGATIVE_KEYWORDS = {

    # Политика
    "выборы": 5,
    "депутат": 4,
    "парламент": 4,
    "сенат": 4,
    "мажилис": 4,
    "президент": 3,
    "правительство": 3,
    "министр": 2,

    # Экономика
    "инфляция": 5,
    "курс тенге": 5,
    "акции": 4,
    "биржа": 4,
    "инвестиции": 3,
    "экономика": 3,

    # Спорт
    "футбол": 6,
    "хоккей": 6,
    "баскетбол": 6,
    "теннис": 6,
    "спорт": 5,
    "матч": 6,
    "чемпионат": 5,

    # Криминал
    "убийство": 5,
    "убил": 5,
    "убита": 5,
    "убит": 5,
    "наркотик": 5,
    "наркотики": 5,
    "наркоторгов": 5,
    "грабеж": 5,
    "ограбление": 5,
    "кража": 5,
    "воровство": 5,
    "мошенничество": 5,
    "взятка": 5,
    "коррупция": 5,

    # Суды
    "суд признал": 5,
    "суд приговорил": 5,
    "приговор": 5,
    "задержан": 4,
    "задержали": 4,

    # Погода без ЧС
    "прогноз погоды": 5,
    "погода на сегодня": 4,
    "погода на завтра": 4,
    "температура воздуха": 4,
}


# ============================================================
# РЕГИОНЫ КАЗАХСТАНА
# ============================================================

# Наличие региона усиливает уверенность,
# что событие относится к Казахстану.

KAZAKHSTAN_REGIONS = [

    "казахстан",
    "рк",

    "астана",
    "алматы",
    "шымкент",

    "акмолинск",
    "акмолинская",

    "актобе",
    "актюбинск",
    "актюбинская",

    "алматинская",
    "область жетысу",
    "жетысу",

    "атырау",
    "атырауская",

    "восточно-казахстанская",
    "вко",
    "восточный казахстан",
    "өскемен",

    "жамбылская",
    "жамбыл",

    "западно-казахстанская",
    "зко",
    "западный казахстан",
    "уральск",

    "карагандинская",
    "карагандинская область",
    "караганда",

    "костанайская",
    "костанай",

    "кызылординская",
    "кызылорда",

    "мангистауская",
    "мангистау",
    "актау",

    "павлодарская",
    "павлодар",

    "северо-казахстанская",
    "ско",
    "северный казахстан",
    "петропавловск",

    "туркестанская",
    "туркестан",

    "абайская",
    "область абай",
    "семей",

    "улитуская",
    "область улытау",
    "жезказган",
]


# ============================================================
# НОРМАЛИЗАЦИЯ ТЕКСТА
# ============================================================

def clean_text(text):
    if not text:
        return ""

    # Удаляем HTML
    text = re.sub(r"<[^>]+>", " ", text)

    # HTML entities
    text = html.unescape(text)

    # Убираем лишние пробелы
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_text(text):
    text = clean_text(text).lower()

    # Ё → Е
    text = text.replace("ё", "е")

    return text


# ============================================================
# РАБОТА С SENT.JSON
# ============================================================

def load_sent():

    if not os.path.exists(SENT_FILE):
        return set()

    try:

        with open(
            SENT_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return set()

        return set(
            str(item)
            for item in data
            if item
        )

    except Exception as e:

        print(
            f"Ошибка чтения {SENT_FILE}: {e}"
        )

        return set()


def save_sent(sent):

    os.makedirs(
        os.path.dirname(SENT_FILE),
        exist_ok=True,
    )

    # Сохраняем максимум последних ссылок.
    sent_list = list(sent)

    if len(sent_list) > MAX_SENT_ITEMS:
        sent_list = sent_list[
            -MAX_SENT_ITEMS:
        ]

    try:

        with open(
            SENT_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                sent_list,
                file,
                ensure_ascii=False,
                indent=2,
            )

    except Exception as e:

        print(
            f"Ошибка сохранения {SENT_FILE}: {e}"
        )


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def get_google_news_url(query):

    encoded_query = quote(
        query,
        safe="",
    )

    return (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}"
        "&hl=ru"
        "&gl=KZ"
        "&ceid=KZ:ru"
    )


# ============================================================
# ДАТА ПУБЛИКАЦИИ
# ============================================================

def get_published_time(entry):

    value = entry.get(
        "published"
    )

    if not value:
        value = entry.get(
            "updated"
        )

    if not value:
        return None

    try:

        published = parsedate_to_datetime(
            value
        )

        if published.tzinfo is None:

            published = published.replace(
                tzinfo=timezone.utc
            )

        return published.astimezone(
            timezone.utc
        )

    except Exception as e:

        print(
            f"Не удалось определить дату публикации: {e}"
        )

        return None


# ============================================================
# ОПРЕДЕЛЕНИЕ ДОМЕНА
# ============================================================

def extract_domain(url):

    try:

        # Убираем протокол
        domain = re.sub(
            r"^https?://",
            "",
            url.lower(),
        )

        # Убираем www.
        domain = re.sub(
            r"^www\.",
            "",
            domain,
        )

        # Убираем путь
        domain = domain.split(
            "/",
            1,
        )[0]

        # Убираем порт
        domain = domain.split(
            ":",
            1,
        )[0]

        return domain

    except Exception:
        return ""


def is_allowed_domain(url):

    domain = extract_domain(
        url
    )

    if not domain:
        return False

    if domain in ALLOWED_DOMAINS:
        return True

    # Разрешаем поддомены:
    # например ru.sputnik.kz
    for allowed in ALLOWED_DOMAINS:

        if domain.endswith(
            "." + allowed
        ):
            return True

    return False


# ============================================================
# ПОЛУЧЕНИЕ НАЗВАНИЯ ИСТОЧНИКА
# ============================================================

def get_source_name(entry):

    try:

        source = entry.get(
            "source"
        )

        if source:

            if hasattr(
                source,
                "get",
            ):

                title = source.get(
                    "title",
                    "",
                )

                if title:
                    return clean_text(
                        title
                    )

    except Exception:
        pass

    return ""


# ============================================================
# ОПРЕДЕЛЕНИЕ ЧС
# ============================================================

def calculate_emergency_score(article):

    title = normalize_text(
        article.get(
            "title",
            "",
        )
    )

    summary = normalize_text(
        article.get(
            "summary",
            "",
        )
    )

    source = normalize_text(
        article.get(
            "source",
            "",
        )
    )

    text = (
        f"{title} "
        f"{summary} "
        f"{source}"
    )

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Сильные признаки
    # --------------------------------------------------------

    for keyword, points in (
        STRONG_EMERGENCY_KEYWORDS.items()
    ):

        if keyword.lower() in text:

            score += points

            reasons.append(
                f"+{points} {keyword}"
            )

    # --------------------------------------------------------
    # Слабые признаки
    # --------------------------------------------------------

    for keyword, points in (
        WEAK_EMERGENCY_KEYWORDS.items()
    ):

        if keyword.lower() in text:

            score += points

            reasons.append(
                f"+{points} {keyword}"
            )

    # --------------------------------------------------------
    # Казахстан / регион
    # --------------------------------------------------------

    has_kazakhstan = False

    for region in KAZAKHSTAN_REGIONS:

        if region.lower() in text:

            has_kazakhstan = True

            score += 2

            reasons.append(
                f"+2 регион:{region}"
            )

            break

    # --------------------------------------------------------
    # Минусы
    # --------------------------------------------------------

    negative_score = 0

    for keyword, points in (
        NEGATIVE_KEYWORDS.items()
    ):

        if keyword.lower() in text:

            negative_score += points

            reasons.append(
                f"-{points} {keyword}"
            )

    score -= negative_score

    # --------------------------------------------------------
    # Специальные комбинации
    # --------------------------------------------------------

    # ДТП само по себе не является достаточным признаком.
    if (
        "дтп" in text
        or "дорожно-транспортное происшествие"
        in text
        or "автокөлік апаты" in text
    ):

        score -= 3

        reasons.append(
            "-3 обычное ДТП"
        )

        # Но ДТП + спасатели / пострадавшие /
        # погибшие / пожар — уже другое дело.

        rescue_words = [
            "спасател",
            "мчс",
            "тжм",
            "құтқар",
            "деблок",
            "пострадал",
            "погиб",
            "пожар",
            "өрт",
            "эвакуа",
        ]

        if any(
            word in text
            for word in rescue_words
        ):

            score += 6

            reasons.append(
                "+6 ДТП с признаками ЧС"
            )

    # --------------------------------------------------------
    # МЧС / ТЖМ + событие
    # --------------------------------------------------------

    has_mchs = (
        "мчс" in text
        or "тжм" in text
        or "төтенше жағдай" in text
    )

    has_event = any(
        keyword.lower() in text
        for keyword in [
            "пожар",
            "өрт",
            "взрыв",
            "жарылыс",
            "наводнение",
            "паводок",
            "подтопление",
            "землетрясение",
            "жер сілкінісі",
            "обрушение",
            "эвакуация",
            "спасатели",
            "құтқарушылар",
            "пропал",
            "утонул",
        ]
    )

    if has_mchs and has_event:

        score += 5

        reasons.append(
            "+5 МЧС/ТЖМ + событие"
        )

    # --------------------------------------------------------
    # Спасатели + конкретное происшествие
    # --------------------------------------------------------

    has_rescuers = any(
        keyword in text
        for keyword in [
            "спасател",
            "құтқар",
        ]
    )

    has_concrete_event = any(
        keyword in text
        for keyword in [
            "пожар",
            "өрт",
            "взрыв",
            "жарылыс",
            "обруш",
            "наводнение",
            "паводок",
            "подтоп",
            "землетряс",
            "эвакуац",
            "пропал",
            "утонул",
            "утону",
            "сел",
            "ополз",
            "лавин",
        ]
    )

    if (
        has_rescuers
        and has_concrete_event
    ):

        score += 5

        reasons.append(
            "+5 спасатели + происшествие"
        )

    return score, reasons, has_kazakhstan


def is_emergency_news(article):

    score, reasons, has_kazakhstan = (
        calculate_emergency_score(
            article
        )
    )

    # Минимальный порог.
    #
    # Если есть явный регион Казахстана,
    # достаточно 5 баллов.
    #
    # Если регион в тексте не указан,
    # требуем немного больше.

    if has_kazakhstan:

        is_relevant = score >= 5

    else:

        is_relevant = score >= 7

    return (
        is_relevant,
        score,
        reasons,
    )


# ============================================================
# ПОЛУЧЕНИЕ НОВОСТЕЙ
# ============================================================

def get_articles():

    articles = []

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            minutes=MAX_AGE_MINUTES
        )
    )

    print("")
    print(
        "Поиск новостей:"
    )

    print(
        f"С {cutoff.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    print(
        f"До {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    print("")

    total_found = 0
    old_news = 0
    future_news = 0
    wrong_source = 0
    irrelevant_news = 0

    # Чтобы один и тот же материал,
    # найденный разными запросами,
    # не анализировать десятки раз.

    seen_urls = set()

    for query in QUERIES:

        print(
            f"Google News → {query}"
        )

        try:

            url = get_google_news_url(
                query
            )

            feed = feedparser.parse(
                url
            )

            for entry in feed.entries:

                total_found += 1

                article_url = (
                    entry.get(
                        "link",
                        "",
                    )
                    .strip()
                )

                if not article_url:
                    continue

                # ------------------------------------------------
                # Проверяем источник
                # ------------------------------------------------

                if not is_allowed_domain(
                    article_url
                ):

                    wrong_source += 1

                    continue

                # ------------------------------------------------
                # Проверяем дату
                # ------------------------------------------------

                published = (
                    get_published_time(
                        entry
                    )
                )

                if not published:
                    continue

                if published < cutoff:

                    old_news += 1

                    continue

                if (
                    published
                    > now
                    + timedelta(
                        minutes=FUTURE_TOLERANCE_MINUTES
                    )
                ):

                    future_news += 1

                    continue

                # ------------------------------------------------
                # Дубликат внутри одного запуска
                # ------------------------------------------------

                if article_url in seen_urls:
                    continue

                seen_urls.add(
                    article_url
                )

                # ------------------------------------------------
                # Данные статьи
                # ------------------------------------------------

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

                source = (
                    get_source_name(
                        entry
                    )
                )

                article = {

                    "title": title,

                    "url": article_url,

                    "published": published,

                    "summary": summary,

                    "source": source,

                }

                # ------------------------------------------------
                # Фильтр ЧС
                # ------------------------------------------------

                (
                    relevant,
                    score,
                    reasons,
                ) = is_emergency_news(
                    article
                )

                if not relevant:

                    irrelevant_news += 1

                    print(
                        f"  [НЕ ЧС {score}] "
                        f"{title}"
                    )

                    if reasons:

                        print(
                            "       "
                            + ", ".join(
                                reasons[:8]
                            )
                        )

                    continue

                # ------------------------------------------------
                # Подходит
                # ------------------------------------------------

                print(
                    f"  [ЧС {score}] "
                    f"{title}"
                )

                if reasons:

                    print(
                        "       "
                        + ", ".join(
                            reasons[:10]
                        )
                    )

                articles.append(
                    article
                )

        except Exception as e:

            print(
                f"Ошибка Google News "
                f"для '{query}': {e}"
            )

    print("")
    print(
        "========================================"
    )
    print(
        "СТАТИСТИКА ПОЛУЧЕНИЯ НОВОСТЕЙ"
    )
    print(
        "========================================"
    )

    print(
        f"Всего результатов Google News: "
        f"{total_found}"
    )

    print(
        f"Старше 60 минут: "
        f"{old_news}"
    )

    print(
        f"Будущая/некорректная дата: "
        f"{future_news}"
    )

    print(
        f"Другие сайты: "
        f"{wrong_source}"
    )

    print(
        f"Нерелевантные: "
        f"{irrelevant_news}"
    )

    print(
        f"Подходящие ЧС: "
        f"{len(articles)}"
    )

    print(
        "========================================"
    )

    return articles


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(article):

    title = html.escape(
        clean_text(
            article["title"]
        )
    )

    source = html.escape(
        clean_text(
            article.get(
                "source",
                "",
            )
        )
    )

    url = article["url"]

    # Ссылка будет отображаться
    # красивой надписью "Открыть новость".

    message = (
        f"<b>{title}</b>"
    )

    if source:

        message += (
            f"\n\nИсточник: {source}"
        )

    message += (
        f'\n\n<a href="'
        f'{html.escape(url, quote=True)}'
        f'">'
        f"Открыть новость"
        f"</a>"
    )

    telegram_url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}"
        "/sendMessage"
    )

    response = requests.post(

        telegram_url,

        data={

            "chat_id":
                TELEGRAM_CHAT_ID,

            "text":
                message,

            "parse_mode":
                "HTML",

            "disable_web_page_preview":
                False,

        },

        timeout=30,
    )

    if not response.ok:

        print(
            f"Telegram ответил: "
            f"{response.status_code}"
        )

        print(
            response.text
        )

    response.raise_for_status()


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():

    print("")
    print(
        "============================================"
    )
    print(
        "       MChS Kazakhstan News Monitor"
    )
    print(
        "============================================"
    )

    print(
        f"Разрешённых источников: "
        f"{len(ALLOWED_DOMAINS)}"
    )

    print(
        f"Поисковых запросов: "
        f"{len(QUERIES)}"
    )

    print(
        f"Период: последние "
        f"{MAX_AGE_MINUTES} минут"
    )

    print(
        "============================================"
    )

    print("")

    # --------------------------------------------------------
    # Загружаем уже отправленные
    # --------------------------------------------------------

    sent = load_sent()

    print(
        f"В базе уже отправленных: "
        f"{len(sent)}"
    )

    print("")

    # --------------------------------------------------------
    # Получаем новости
    # --------------------------------------------------------

    articles = get_articles()

    # --------------------------------------------------------
    # Убираем дубли по URL
    # --------------------------------------------------------

    unique_articles = {}

    for article in articles:

        url = article["url"]

        if url not in unique_articles:

            unique_articles[url] = article

    articles = list(
        unique_articles.values()
    )

    # --------------------------------------------------------
    # Сортировка от самых новых
    # --------------------------------------------------------

    articles.sort(

        key=lambda article:
            article["published"],

        reverse=True,

    )

    print("")
    print(
        f"После удаления дублей: "
        f"{len(articles)}"
    )

    print("")

    # --------------------------------------------------------
    # Отправка
    # --------------------------------------------------------

    new_count = 0
    duplicate_count = 0
    send_error_count = 0

    for article in articles:

        url = article["url"]

        # ----------------------------------------------------
        # Уже отправляли
        # ----------------------------------------------------

        if url in sent:

            duplicate_count += 1

            print(
                f"[DUPLICATE] "
                f"{article['title']}"
            )

            continue

        # ----------------------------------------------------
        # Отправляем
        # ----------------------------------------------------

        try:

            send_telegram(
                article
            )

            # Добавляем в sent только после
            # успешной отправки.

            sent.add(
                url
            )

            new_count += 1

            published_local = (
                article["published"]
                .astimezone()
                .strftime(
                    "%d.%m.%Y %H:%M"
                )
            )

            score, reasons, _ = (
                calculate_emergency_score(
                    article
                )
            )

            print("")

            print(
                f"[ОТПРАВЛЕНО] "
                f"[{published_local}] "
                f"[score={score}]"
            )

            print(
                article["title"]
            )

            print(
                f"Источник: "
                f"{article.get('source', '')}"
            )

            print(
                f"URL: {url}"
            )

        except Exception as e:

            send_error_count += 1

            print("")

            print(
                f"[ОШИБКА TELEGRAM] "
                f"{article['title']}"
            )

            print(
                str(e)
            )

    # --------------------------------------------------------
    # Сохраняем sent.json
    # --------------------------------------------------------

    save_sent(
        sent
    )

    # --------------------------------------------------------
    # Итог
    # --------------------------------------------------------

    print("")
    print(
        "============================================"
    )
    print(
        "                    ИТОГ"
    )
    print(
        "============================================"
    )

    print(
        f"Новых отправлено: "
        f"{new_count}"
    )

    print(
        f"Уже были отправлены: "
        f"{duplicate_count}"
    )

    print(
        f"Ошибок Telegram: "
        f"{send_error_count}"
    )

    print(
        f"Всего в sent.json: "
        f"{len(sent)}"
    )

    print(
        "============================================"
    )

    print("")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
