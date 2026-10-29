import os
import random
import re
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT")

# Надежные источники, где регулярно публикуются обзоры аукционов, цен и продаж (например, eBay Watch)
SOURCES = [
    {"name": "PokeBeach", "url": "https://www.pokebeach.com/"},
    {"name": "PokeGuardian", "url": "https://www.pokeguardian.com/"},
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


def run():
  print("--- ЗАПУСК АУКЦИОННОГО БОТА (ТРЕКИНГ ПРОДАЖ И ЦЕН) ---")
  if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ Ошибка: Не заданы секреты TG_TOKEN или TG_CHAT!")
    return

  last_link = ""
  if os.path.exists("last_auction.txt"):
    with open("last_auction.txt", "r", encoding="utf-8") as f:
      last_link = f.read().strip()

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  target_article = None

  # Проходим по источникам в поисках материалов про продажи, аукционы и цены
  for source in SOURCES:
    try:
      print(f"Сканирую ресурс: {source['name']}")
      response = requests.get(source["url"], headers=headers, timeout=15)
      if response.status_code != 200:
        continue

      soup = BeautifulSoup(response.text, "html.parser")
      articles = soup.find_all("article")

      for article in articles:
        title_tag = article.find("h2") or article.find("h1") or article.find("a")
        if not title_tag:
          continue

        link_tag = title_tag.find("a") if title_tag.name != "a" else title_tag
        if not link_tag or not link_tag.has_attr("href"):
          continue

        link = link_tag["href"]
        title = link_tag.get_text(strip=True)

        # Ключевые слова, которые указывают на рыночную сводку, аукцион или продажи
        market_keywords = [
            "ebay",
            "sale",
            "sold",
            "price",
            "market",
            "auction",
            "worth",
            "record",
        ]
        if any(kw in title.lower() for kw in market_keywords):
          if link != last_link:
            target_article = {"title": title, "link": link, "source": source["name"]}
            # Ищем качественное изображение лота или карты в статье
            img = article.find("img")
            target_article["image_url"] = img.get("src", "") if img else ""
            break
      if target_article:
        break
    except Exception as e:
      print(f"Ошибка при обработке {source['name']}: {e}")

  if not target_article:
    print("ℹ️ Новых отчетов по аукционам и продажам на сайтах не обнаружено.")
    return

  title = target_article["title"]
  link = target_article["link"]
  image_url = target_article["image_url"]

  print(f"Найдена сводка аукционов: {title}")
  print(f"Ссылка: {link}")

  # Загружаем полный текст статьи с результатами торгов
  full_text = ""
  try:
    art_response = requests.get(link, headers=headers, timeout=15)
    if art_response.status_code == 200:
      art_soup = BeautifulSoup(art_response.text, "html.parser")
      content_div = (
          art_soup.find("div", class_="entry-content")
          or art_soup.find("div", class_="post-content")
          or art_soup.find("article")
      )
      if content_div:
        paragraphs = content_div.find_all("p")
        full_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs])
  except Exception as e:
    print(f"Ошибка загрузки текста статьи: {e}")

  if not full_text:
    full_text = "Детали торгов и итоговые цены смотрите в источнике!"

  print("Перевожу отчет о продажах на русский язык...")
  ru_title = translate_text(title)
  ru_body = translate_text(full_text)

  if len(ru_body) > 850:
    ru_body = ru_body[:850] + "...\n\n*(Текст сокращен, читайте подробности в источнике)*"

  intros = [
      "💰 **РЫНОЧНЫЙ ДАЙДЖЕСТ: ЗА СКОЛЬКО УХОДЯТ ТОПОВЫЕ КАРТЫ?!**",
      "📈 **АУКЦИОННЫЕ РЕКОРДЫ И СВЕЖИЕ ПРОДАЖИ!**",
      "💎 **БИРЖА ПОКЕМОНОВ: СКОЛЬКО СТОЯТ САМЫЕ РЕДКИЕ ЛОТЫ?**",
      "🔥 **ОТЧЕТ ПО ПРОДАЖАМ НА ТОРГАХ!**",
  ]

  post_text = (
      f"{random.choice(intros)}\n\n📌 **{ru_title}**\n\n{ru_body}\n\n🔗 [Смотреть"
      f" полные результаты аукциона]({link})"
  )

  # Отправляем в Telegram (с картинкой лота/карты или текстом)
  if image_url:
    print(f"Отправляем отчет с изображением: {image_url}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": post_text,
        "parse_mode": "Markdown",
    }
  else:
    print("Изображение не найдено, отправляем текстовый отчет.")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": post_text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

  response = requests.post(url, json=payload)
  print(f"Ответ Telegram API: {response.status_code}")
  print(f"Текст ответа: {response.text}")

  if response.status_code == 200:
    print("✅ УСПЕШНО! Отчет по аукционам опубликован в канале.")
    with open("last_auction.txt", "w", encoding="utf-8") as f:
      f.write(link)
  else:
    print("❌ Ошибка отправки сообщения в Telegram!")


run()
