import os
import json
import time
import random
import logging
from threading import Thread
from datetime import datetime, date
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("TravelRadar")

# --- КОНФИГУРАЦИЯ И КЛЮЧИ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "9157486685:AAH9b63VOb42mQFcf6hPR_Xrvr5stjZViJ4")
MY_CHAT_ID = os.getenv("MY_CHAT_ID", "@radar_travel_tg")

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "decbc99d1f0432b2043ff2075dcc8410")
MARKER = os.getenv("MARKER", "805655")

CHANNEL_LINK = "https://max.ru/channel_radar_travel"
CACHE_FILE = "sent_deals_cache.json"

SCAN_INTERVAL = 2400       # 40 минут
MAX_POSTS_PER_CYCLE = 4
MAX_DAYS_AHEAD = 90
HOT_DAYS_THRESHOLD = 14
MIN_DISCOUNT = 15

ORIGINS = {
    "SVX": {"name": "Екатеринбург", "tag": "#изЕкатеринбурга"},
    "TJM": {"name": "Тюмень", "tag": "#изТюмени"},
    "SGC": {"name": "Сургут", "tag": "#изСургута"},
    "OVB": {"name": "Новосибирск", "tag": "#изНовосибирска"},
    "IKT": {"name": "Иркутск", "tag": "#изИркутска"},
    "MOW": {"name": "Москва", "tag": "#изМосквы"},
    "LED": {"name": "Санкт-Петербург", "tag": "#изПетербурга"}
}

AIRLINES = {
    "SU": "Аэрофлот", "S7": "S7 Airlines", "DP": "Победа",
    "U6": "Уральские авиалинии", "UT": "UTair", "N4": "Nordwind",
    "EO": "Ikar", "5N": "Smartavia", "WZ": "Red Wings",
    "A4": "Азимут", "FV": "Россия", "IO": "IrAero",
    "Y7": "NordStar", "TK": "Turkish Airlines", "FZ": "Flydubai",
    "G9": "Air Arabia", "PC": "Pegasus", "MS": "EgyptAir",
    "HY": "Uzbekistan Airways", "KC": "Air Astana", "B2": "Belavia",
    "3U": "Sichuan Airlines", "HU": "Hainan Airlines", "CA": "Air China",
    "MU": "China Eastern"
}

CITY_DATA = {
    "HKT": {"name": "Пхукет, Таиланд 🇹🇭", "tag": "#Пхукет #Таиланд", "photo": "https://images.unsplash.com/photo-1589394815804-964ed0be2eb5?auto=format&fit=crop&w=1000&q=80"},
    "BKK": {"name": "Бангкок, Таиланд 🇹🇭", "tag": "#Бангкок #Таиланд", "photo": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1000&q=80"},
    "CXR": {"name": "Нячанг, Вьетнам 🇻🇳", "tag": "#Нячанг #Вьетнам", "photo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1000&q=80"},
    "AYT": {"name": "Анталья, Турция 🇹🇷", "tag": "#Анталья #Турция", "photo": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1000&q=80"},
    "IST": {"name": "Стамбул, Турция 🇹🇷", "tag": "#Стамбул #Турция", "photo": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1000&q=80"},
    "DLM": {"name": "Даламан, Турция 🇹🇷", "tag": "#Даламан #Турция", "photo": "https://images.unsplash.com/photo-1527631746610-bca00a040d60?auto=format&fit=crop&w=1000&q=80"},
    "DXB": {"name": "Дубай, ОАЭ 🇦🇪", "tag": "#Дубай #ОАЭ", "photo": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1000&q=80"},
    "SHJ": {"name": "Шарджа, ОАЭ 🇦🇪", "tag": "#Шарджа #ОАЭ", "photo": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?auto=format&fit=crop&w=1000&q=80"},
    "SSH": {"name": "Шарм-эль-Шейх, Египет 🇪🇬", "tag": "#ШармЭльШейх #Египет", "photo": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?auto=format&fit=crop&w=1000&q=80"},
    "HRG": {"name": "Хургада, Египет 🇪🇬", "tag": "#Хургада #Египет", "photo": "https://images.unsplash.com/photo-1568322445074-8f8501e514e2?auto=format&fit=crop&w=1000&q=80"},
    "AER": {"name": "Сочи, Россия 🇷🇺", "tag": "#Сочи #Море", "photo": "https://images.unsplash.com/photo-1569683795645-b62e50fbf103?auto=format&fit=crop&w=1000&q=80"},
    "MRV": {"name": "Минеральные Воды 🇷🇺", "tag": "#МинВоды #Кавказ", "photo": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1000&q=80"},
    "KGD": {"name": "Калининград, Россия 🇷🇺", "tag": "#Калининград #Балтика", "photo": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1000&q=80"},
    "SYX": {"name": "Хайнань (Санья), Китай 🇨🇳", "tag": "#Хайнань #Китай", "photo": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80"},
    "PEK": {"name": "Пекин, Китай 🇨🇳", "tag": "#Пекин #Китай", "photo": "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?auto=format&fit=crop&w=1000&q=80"},
    "EVN": {"name": "Ереван, Армения 🇦🇲", "tag": "#Ереван #Армения", "photo": "https://images.unsplash.com/photo-1561571442-9382f768018e?auto=format&fit=crop&w=1000&q=80"},
    "TBS": {"name": "Тбилиси, Грузия 🇬🇪", "tag": "#Тбилиси #Грузия", "photo": "https://images.unsplash.com/photo-1562887189-e5d078343de6?auto=format&fit=crop&w=1000&q=80"},
    "DPS": {"name": "Бали, Индонезия 🇮🇩", "tag": "#Бали #Индонезия", "photo": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=1000&q=80"},
    "GOI": {"name": "Гоа, Индия 🇮🇳", "tag": "#Гоа #Индия", "photo": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=1000&q=80"}
}

MONTHS_RU = {1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня", 7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"}
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)
session = requests.Session()
app = Flask(__name__)

@app.route("/")
def health_check():
    return "Travel Radar Bot is running 24/7!", 200

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_cache(cache_set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(cache_set)[-1500:], f)
    except Exception:
        pass

already_sent = load_cache()

def format_price(value):
    return f"{int(value):,}".replace(",", " ")

def pluralize_nights(n):
    if 11 <= n % 100 <= 19:
        return f"{n} ночей"
    rem = n % 10
    if rem == 1:
        return f"{n} ночь"
    if 2 <= rem <= 4:
        return f"{n} ночи"
    return f"{n} ночей"

def format_transfers(count):
    if count == 0:
        return "Прямой рейс без пересадок"
    elif count == 1:
        return "1 короткая пересадка"
    return f"{count} пересадки"

def format_human_date(d_obj):
    return f"{d_obj.day} {MONTHS_RU[d_obj.month]} ({DAYS_RU[d_obj.weekday()]})"

def fetch_flights(origin_code, one_way="true"):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {"origin": origin_code, "currency": "rub", "sorting": "price", "one_way": one_way, "limit": 100, "token": TRAVELPAYOUTS_TOKEN}
    try:
        res = session.get(url, params=params, timeout=15)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        logger.error(f"Ошибка сети ({origin_code}): {e}")
    return []

def build_post_card(d):
    is_hot = d["days_left"] <= HOT_DAYS_THRESHOLD
    if d["discount"] >= 35:
        badge = "🚨🔥 <b>АНОМАЛЬНОЕ ПАДЕНИЕ ЦЕНЫ!</b>" if is_hot else "💎🔥 <b>РАННЕЕ БРОНИРОВАНИЕ: СУПЕРЦЕНА!</b>"
    elif is_hot:
        badge = f"🔥 <b>ГОРЯЩИЙ ВЫЛЕТ (СКИДКА {d['discount']}%)</b>"
    else:
        badge = f"🗓 <b>ОТПУСК НАПЕРЕД (ВЫГОДА {d['discount']}%)</b>"

    urgency = "⚡️ <i>Вылет совсем скоро! Количество мест по этому тарифу ограничено.</i>" if is_hot else "🧳 <i>Идеально, чтобы спланировать отпуск заранее без переплат!</i>"

    text = (
        f"{badge}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
        f"📅 <b>Даты:</b> {d['dates_human']}\n"
        f"🔄 <b>Формат:</b> {d['trip_type']}\n"
        f"✈️ <b>Рейс:</b> {d['airline']} • {d['transfer_str']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>На одного:</b> {format_price(d['price_1'])} ₽ <s>{format_price(d['avg_1'])} ₽</s>\n"
        f"👥 <b>На двоих: {format_price(d['price_2'])} ₽</b> <i>(выгода {format_price(d['saved_2'])} ₽!)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{urgency}\n\n"
        f"📡 <b>Все горящие туры в нашем MAX:</b>\n"
        f"👉 <a href='{CHANNEL_LINK}'><b>Подписаться на Радар Путешествий</b></a>\n\n"
        f"{d['hashtags']}"
    )

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text=f"🎟 Билет на 1 чел. — {format_price(d['price_1'])} ₽", url=d["link_1"]),
        InlineKeyboardButton(text=f"👩‍❤️‍👨 Забрать на двоих — {format_price(d['price_2'])} ₽", url=d["link_2"]),
        InlineKeyboardButton(text="📲 Открыть канал в мессенджере MAX", url=CHANNEL_LINK)
    )
    return text, markup

def publish_deal(deal_data):
    caption_text, reply_markup = build_post_card(deal_data)
    try:
        bot.send_photo(chat_id=MY_CHAT_ID, photo=deal_data["photo"], caption=caption_text, parse_mode="HTML", reply_markup=reply_markup)
        logger.info(f"Опубликовано: {deal_data['orig_name']} -> {deal_data['dest_name']}")
        return True
    except Exception as e:
        logger.error(f"Ошибка публикации в Telegram: {e}")
        return False

def run_radar_cycle():
    global already_sent
    today = date.today()
    candidates = []
    origin_items = list(ORIGINS.items())
    random.shuffle(origin_items)

    for orig_code, orig_meta in origin_items:
        flights = fetch_flights(orig_code, "false") + fetch_flights(orig_code, "true")
        if not flights:
            continue

        dest_prices = {}
        for f in flights:
            d_code = f.get("destination")
            p = f.get("price") or f.get("value")
            if d_code and p:
                dest_prices.setdefault(f"{d_code}_{'RT' if f.get('return_at') else 'OW'}", []).append(p)

        dest_avg = {k: sum(v) / len(v) for k, v in dest_prices.items()}

        for f in flights:
            dest_code = f.get("destination")
            price_1 = f.get("price") or f.get("value")
            dep_at = f.get("departure_at", "")[:10]
            ret_at = f.get("return_at", "")[:10]
            if not price_1 or not dep_at or dest_code not in CITY_DATA:
                continue

            try:
                dep_date = datetime.strptime(dep_at, "%Y-%m-%d").date()
                days_left = (dep_date - today).days
                if not (0 <= days_left <= MAX_DAYS_AHEAD):
                    continue
            except ValueError:
                continue

            flight_id = f"{orig_code}_{dest_code}_{dep_at}_{ret_at}_{price_1}"
            if flight_id in already_sent:
                continue

            avg_1 = dest_avg.get(f"{dest_code}_{'RT' if ret_at else 'OW'}", price_1)
            if price_1 >= avg_1:
                continue

            discount = int((1 - (price_1 / avg_1)) * 100)
            if discount < MIN_DISCOUNT:
                continue

            avg_1_int = int(avg_1)
            price_2 = price_1 * 2
            saved_2 = (avg_1_int * 2) - price_2
            ddmm_dep = dep_at[8:10] + dep_at[5:7]

            if ret_at:
                try:
                    ret_date = datetime.strptime(ret_at, "%Y-%m-%d").date()
                    nights = (ret_date - dep_date).days
                    if nights <= 0:
                        continue
                    ddmm_ret = ret_at[8:10] + ret_at[5:7]
                    dates_human = f"{format_human_date(dep_date)} – {format_human_date(ret_date)}"
                    trip_type = f"Туда-обратно ({pluralize_nights(nights)})"
                    search_route = f"{orig_code}{ddmm_dep}{dest_code}{ddmm_ret}"
                except ValueError:
                    continue
            else:
                when_label = "Уже сегодня!" if days_left == 0 else ("Уже завтра!" if days_left == 1 else f"через {days_left} дн.")
                dates_human = f"{format_human_date(dep_date)} ({when_label})"
                trip_type = "Перелет в одну сторону"
                search_route = f"{orig_code}{ddmm_dep}{dest_code}"

            dest_info = CITY_DATA[dest_code]
            airline_code = f.get("airline", "")
            candidates.append({
                "flight_id": flight_id,
                "orig_name": orig_meta["name"],
                "dest_name": dest_info["name"],
                "photo": dest_info["photo"],
                "dates_human": dates_human,
                "days_left": days_left,
                "trip_type": trip_type,
                "airline": AIRLINES.get(airline_code, f"Рейс {airline_code}" if airline_code else "Регулярный рейс"),
                "transfer_str": format_transfers(f.get("transfers", 0)),
                "discount": discount,
                "price_1": price_1,
                "avg_1": avg_1_int,
                "price_2": price_2,
                "saved_2": saved_2,
                "link_1": f"https://www.aviasales.ru/search/{search_route}1?marker={MARKER}",
                "link_2": f"https://www.aviasales.ru/search/{search_route}2?marker={MARKER}",
                "hashtags": f"{orig_meta['tag']} {dest_info['tag']} {'#горящийтур' if days_left <= HOT_DAYS_THRESHOLD else '#раннеебронирование'}"
            })
        time.sleep(1)

    candidates.sort(key=lambda x: x["discount"], reverse=True)
    sent_count = 0
    used_routes = set()

    for deal in candidates:
        route_key = f"{deal['orig_name']}_{deal['dest_name']}"
        if route_key in used_routes:
            continue
        if publish_deal(deal):
            already_sent.add(deal["flight_id"])
            used_routes.add(route_key)
            sent_count += 1
            save_cache(already_sent)
            time.sleep(3.5)
        if sent_count >= MAX_POSTS_PER_CYCLE:
            break

def background_worker():
    while True:
        try:
            run_radar_cycle()
        except Exception as e:
            logger.error(f"Сбой цикла: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    Thread(target=background_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
