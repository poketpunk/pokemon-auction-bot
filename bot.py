import os
import random
import urllib.parse
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT")

# Поисковые запросы для сбора главных новостей об аукционах и продажах карт
SEARCH_QUERIES = [
    '"Pokemon TCG" auction sale record',
    '"Pokemon card" sold price goldin ebay',
]


def translate_text(text):
  if not text:
    return ""
  try:
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "ru",
        "dt": "t",
        "q": text[:4000],
    }
    response = requests.get(url, params=params, timeout=10)
    if response.status_code == 200:
      data = response.json()
      return "".join([item[0] for item in data[0] if item[0]])
  except Exception as e:
    print(f"Ошибка перевода: {e}")
  return text


def fetch_news_items():
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }
  collected_news = []

  for query in SEARCH_QUERIES:
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    try:
      response = requests.get(rss_url, headers=headers, timeout=15)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "xml")
        items = soup.find_all("item")

        # Собираем свежие статьи
        for item in items[:4]:
          title = item.title.text if item.title else ""
          link = item.link.text if item.link else ""
          if title and link:
            collected_news.append({"title": title, "link": link})
    except Exception as e:
      print(f"Ошибка поиска для запроса '{query}': {e}")

  # Убираем дубликаты
  unique_news = []
  seen_links = set()
  for news in collected_news:
    if news["link"] not in seen_links:
      seen_links.add(news["link"])
      unique_news.append(news)

  return unique_news


def run():
  print("--- ЗАПУСК БОТА (ГЕНЕРАЦИЯ ДАЙДЖЕСТА СВОДОК) ---")
  if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ Ошибка: Не заданы секреты TG_TOKEN или TG_CHAT!")
    return

  # Читаем историю отправленных ссылок, чтобы не дублировать новости
  sent_links = set()
  if os.path.exists("sent_links.txt"):
    with open("sent_links.txt", "r", encoding="utf-8") as f:
      sent_links = set(line.strip() for line in f if line.strip())

  all_news = fetch_news_items()
  if not all_news:
    print("ℹ️ Свежих новостей в Google News не найдено.")
    return

  # Оставляем только то, чего мы еще не публиковали
  new_items = [n for n in all_news if n["link"] not in sent_links]

  if not new_items:
    print("ℹ️ Новых уникальных статей для дайджеста нет.")
    return

  # Берем до 4 свежих новостей для формирования красивого единого поста
  digest_batch = new_items[:4]
  print(f"Найдено новых материалов для дайджеста: {len(digest_batch)}")

  digest_lines = [
      "📊 **ГЛАВНЫЕ НОВОСТИ И АУКЦИОННЫЕ СВОДКИ POKÉMON TCG:**\n"
  ]

  new_links_to_save = []

  for idx, item in enumerate(digest_batch, 1):
    orig_title = item["title"]
    link = item["link"]

    print(f"Перевожу заголовок: {orig_title}")
    ru_title = translate_text(orig_title)

    digest_lines.append(f"• **{ru_title}**\n  🔗 [Читать источник]({link})\n")
    new_links_to_save.append(link)

  footer_variants = [
      "\n💬 *Как вам такие ценники? Делитесь мнением в комментариях!*",
      "\n🔥 *Какой лот удивил вас больше всего? Пишите в чате!*",
      "\n⚡ *Рынок коллекционных карт продолжает ставить рекорды. Следим дальше!*",
  ]
  digest_lines.append(random.choice(footer_variants))

  post_text = "\n".join(digest_lines)

  if len(post_text) > 4000:
    post_text = post_text[:4000] + "\n...(дайджест сокращен)"

  # Отправляем единый аналитический пост в Telegram
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": post_text,
      "parse_mode": "Markdown",
      "disable_web_page_preview": True,
  }

  response = requests.post(url, json=payload)
  print(f"Ответ Telegram API: {response.status_code}")

  if response.status_code == 200:
    print("✅ УСПЕШНО! Дайджест новостей опубликован одним постом.")
    with open("sent_links.txt", "a", encoding="utf-8") as f:
      for l in new_links_to_save:
        f.write(l + "\n")
  else:
    print("❌ Ошибка отправки дайджеста в Telegram!")


run()
