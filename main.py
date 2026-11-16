import os
json_lib = __import__('json')
import time
import random
import logging
from threading import Thread
from datetime import datetime, date, timedelta, timezone
import requests
from flask import Flask, redirect, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MaxTravelEngine")

# Жестко фиксируем рабочий токен и ID вашего канала в MAX
MAX_BOT_TOKEN = "F9LHodD0cOKKyq5NS6jf921Uz0yHO2YyMY2NxT-IuC6D0kJPOxOXbUUuX1D1lVcPc8XKbyKsv7rAQI5yhH9p"
MAX_CHAT_ID = "-81280102401406"

MAX_API_URLS = ["https://platform-api.max.ru", "https://botapi.max.ru"]

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "decbc99d1f0432b2043ff2075dcc8410")
MARKER = os.getenv("MARKER", "805655")

CHANNEL_LINK = "https://max.ru/se15023987_biz"
CACHE_FILE = "max_radar_state.json"

LOCAL_TZ = timezone(timedelta(hours=5))
SCAN_INTERVAL = 2400
MAX_DEALS_PER_CYCLE = 3
MAX_DAYS_AHEAD = 90
HOT_DAYS_THRESHOLD = 14
MIN_TOUR_DISCOUNT = 14
MIN_FLIGHT_DISCOUNT = 25

EDITORIAL_SLOTS = {"morning": 9, "afternoon": 14, "evening": 19}

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
    "HKT": {
        "name": "Пхукет, Таиланд 🇹🇭", "en": "Phuket", "tag": "#Пхукет #Таиланд",
        "hotel_base_2p": 4200, "meal": "Завтраки включены (BB)", "stars": "4★ Курортный отель",
        "photo": "https://images.unsplash.com/photo-1589394815804-964ed0be2eb5?auto=format&fit=crop&w=1200&q=85"
    },
    "BKK": {
        "name": "Паттайя / Бангкок, Таиланд 🇹🇭", "en": "Bangkok", "tag": "#Таиланд #Паттайя",
        "hotel_base_2p": 3500, "meal": "Завтраки включены (BB)", "stars": "4★ Отель у моря",
        "photo": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1200&q=85"
    },
    "CXR": {
        "name": "Нячанг, Вьетнам 🇻🇳", "en": "Nha Trang", "tag": "#Нячанг #Вьетнам",
        "hotel_base_2p": 3100, "meal": "Завтраки (BB)", "stars": "4★ Первая линия",
        "photo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1200&q=85"
    },
    "AYT": {
        "name": "Анталья / Кемер, Турция 🇹🇷", "en": "Antalya", "tag": "#Анталья #Турция",
        "hotel_base_2p": 5800, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Курортный спа-отель",
        "photo": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1200&q=85"
    },
    "IST": {
        "name": "Стамбул, Турция 🇹🇷", "en": "Istanbul", "tag": "#Стамбул #Турция",
        "hotel_base_2p": 4600, "meal": "Завтраки (BB)", "stars": "4★ Исторический центр",
        "photo": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1200&q=85"
    },
    "DXB": {
        "name": "Дубай, ОАЭ 🇦🇪", "en": "Dubai", "tag": "#Дубай #ОАЭ",
        "hotel_base_2p": 6900, "meal": "Завтраки (BB)", "stars": "4★ Отель с бассейном",
        "photo": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1200&q=85"
    },
    "SHJ": {
        "name": "Шарджа, ОАЭ 🇦🇪", "en": "Sharjah", "tag": "#Шарджа #ОАЭ",
        "hotel_base_2p": 5200, "meal": "Завтрак + Ужин (HB)", "stars": "4★ Пляжный отель",
        "photo": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?auto=format&fit=crop&w=1200&q=85"
    },
    "SSH": {
        "name": "Шарм-эль-Шейх, Египет 🇪🇬", "en": "Sharm El Sheikh", "tag": "#ШармЭльШейх #Египет",
        "hotel_base_2p": 5600, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Коралловый риф",
        "photo": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?auto=format&fit=crop&w=1200&q=85"
    },
    "HRG": {
        "name": "Хургада, Египет 🇪🇬", "en": "Hurghada", "tag": "#Хургада #Египет",
        "hotel_base_2p": 5100, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Песчаный пляж",
        "photo": "https://images.unsplash.com/photo-1568322445074-8f8501e514e2?auto=format&fit=crop&w=1200&q=85"
    },
    "SYX": {
        "name": "о. Хайнань (Санья), Китай 🇨🇳", "en": "Sanya", "tag": "#Хайнань #Китай",
        "hotel_base_2p": 4800, "meal": "Завтраки (BB)", "stars": "4–5★ Тропический резорт",
        "photo": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=85"
    },
    "AER": {
        "name": "Сочи / Адлер, Россия 🇷🇺", "en": "Sochi", "tag": "#Сочи #ЧерноеМоре",
        "hotel_base_2p": 3800, "meal": "Завтраки (BB)", "stars": "4★ Отель у побережья",
        "photo": "https://images.unsplash.com/photo-1569683795645-b62e50fbf103?auto=format&fit=crop&w=1200&q=85"
    },
    "KGD": {
        "name": "Калининград и Балтика 🇷🇺", "en": "Kaliningrad", "tag": "#Калининград #Балтика",
        "hotel_base_2p": 3600, "meal": "Завтраки (BB)", "stars": "4★ Бутик-отель",
        "photo": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1200&q=85"
    },
    "DPS": {
        "name": "о. Бали, Индонезия 🇮🇩", "en": "Bali", "tag": "#Бали #Индонезия",
        "hotel_base_2p": 4500, "meal": "Завтраки (BB)", "stars": "4★ Вилла / Резорт с бассейном",
        "photo": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=1200&q=85"
    }
}

EDITORIAL_POSTS = {
    "morning": [
        {
            "id": "m_vietnam_season",
            "badge": "☀️ УТРЕННИЙ ГИД • КУДА ЛЕТЕТЬ",
            "title": "Почему Нячанг снова стал главным хитом пляжного отдыха",
            "body": (
                "Вьетнам радует мягким климатом, чистым морем и очень доступными ценами внутри страны.\n\n"
                "• <b>Безвизовый въезд:</b> до 45 дней по загранпаспорту без сложных анкет и сборов.\n"
                "• <b>Питание и фрукты:</b> ужин с морепродуктами на двоих обходится в 1 200–1 800 ₽.\n"
                "• <b>Отельная база:</b> высотные отели 4–5★ с панорамными бассейнами на крыше по цене обычных «троек»."
            ),
            "tip": "Выбирайте отели на первой и второй линии в районе Европейского квартала — вся инфраструктура и пляж будут в 3 минутах ходьбы.",
            "photo": "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=1200&q=85",
            "tags": "#гидпутешественника #Вьетнам #Нячанг"
        }
    ],
    "afternoon": [
        {
            "id": "a_baggage_rules",
            "badge": "🧳 ПАМЯТКА ТУРИСТА • БАГАЖ",
            "title": "Как собрать ручную кладь и не доплачивать в аэропорту",
            "body": (
                "Даже в безбагажных тарифах можно комфортно улететь в отпуск на 7–10 дней, зная правила перевозчиков.\n\n"
                "• <b>Сверх нормы бесплатно:</b> верхняя одежда, дамская сумка или портфель и покупки из Duty Free.\n"
                "• <b>Жидкости в салон:</b> флаконы до 100 мл каждый в одном прозрачном пакете.\n"
                "• <b>Пауэрбанки:</b> перевозятся строго в ручной клади — сдавать их в багаж запрещено."
            ),
            "tip": "Перед выездом в аэропорт взвесьте ручную кладь дома: перевес на стойке регистрации стоит в 3 раза дороже онлайн-оплаты.",
            "photo": "https://images.unsplash.com/photo-1553531384-cc64ac80f931?auto=format&fit=crop&w=1200&q=85",
            "tags": "#памяткатуриста #лайфхак #авиаперелет"
        }
    ],
    "evening": [
        {
            "id": "e_phuket_beaches",
            "badge": "🌅 ВЕЧЕРНЯЯ АТМОСФЕРА • ЛУЧШИЕ ПЛЯЖИ",
            "title": "Три самых живописных пляжа Пхукета для идеальных закатов",
            "body": (
                "Пхукет — это десятки разных бухт, каждая со своим характером и атмосферой.\n\n"
                "• <b>Ката Ной (Kata Noi):</b> уютная камерная бухта с бирюзовой водой и мягким песком.\n"
                "• <b>Най Харн (Nai Harn):</b> пляж на юге острова, окруженный зелеными холмами и смотровой площадкой Промтхеп.\n"
                "• <b>Банг Тао (Bang Tao):</b> шестикилометровая полоса песка с хвойными деревьями."
            ),
            "tip": "Приезжайте на мыс Промтхеп за 40 минут до заката — оттуда открывается лучший вид на Андаманское море.",
            "photo": "https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?auto=format&fit=crop&w=1200&q=85",
            "tags": "#вечернийдайджест #Пхукет #пляжимира"
        }
    ]
}

MONTHS_RU = {1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня", 7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"}
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

session = requests.Session()
app = Flask(__name__)

diag_info = {
    "active_api": MAX_API_URLS[0],
    "bot_profile": "Проверяется...",
    "last_api_debug": "Ожидание запроса...",
    "last_send_status": "Ожидание отправки...",
    "posts_sent_count": 0
}

def load_state():
    default_state = {"sent_deals": [], "editorial_log": {}, "editorial_index": {"morning": 0, "afternoon": 0, "evening": 0}}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                default_state.update(json_lib.load(f))
        except Exception:
            pass
    return default_state

def save_state(state):
    try:
        state["sent_deals"] = state["sent_deals"][-1500:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json_lib.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Ошибка сохранения: {e}")

bot_state = load_state()

def max_api_request(method, path, params=None, json_data=None, files=None, timeout=12):
    token = MAX_BOT_TOKEN
    params = dict(params or {})
    for base_url in MAX_API_URLS:
        headers_a = {"Authorization": token}
        try:
            res = session.request(method, f"{base_url}{path}", headers=headers_a, params=params, json=json_data, files=files, timeout=timeout)
            if res.status_code in (200, 201):
                diag_info["active_api"] = base_url
                return res
            diag_info["last_api_debug"] = f"{path} ({base_url}): HTTP {res.status_code} — {res.text[:150]}"
        except Exception as e:
            diag_info["last_api_debug"] = f"Ошибка {base_url}{path}: {e}"
        
        params_b = dict(params)
        params_b["access_token"] = token
        try:
            res_b = session.request(method, f"{base_url}{path}", params=params_b, json=json_data, files=files, timeout=timeout)
            if res_b.status_code in (200, 201):
                diag_info["active_api"] = base_url
                return res_b
        except Exception:
            pass
    return None

def check_bot_identity():
    res = max_api_request("GET", "/me")
    if res:
        data = res.json()
        name = data.get("name") or data.get("first_name") or "Бот"
        username = data.get("username") or "без_ника"
        uid = data.get("user_id")
        diag_info["bot_profile"] = f"{name} (@{username}, ID: {uid})"
    else:
        diag_info["bot_profile"] = f"Ошибка токена! ({diag_info['last_api_debug']})"

def upload_image_to_max(photo_url):
    up_init = max_api_request("POST", "/uploads", params={"type": "image"})
    if up_init:
        upload_url = up_init.json().get("url")
        if upload_url:
            try:
                img_resp = session.get(photo_url, timeout=12)
                if img_resp.status_code == 200:
                    files = {"data": ("cover.jpg", img_resp.content, "image/jpeg")}
                    up_done = session.post(upload_url, files=files, timeout=20)
                    if up_done.status_code == 200:
                        time.sleep(2.0)
                        return up_done.json()
            except Exception:
                pass
    return {"url": photo_url}

def send_to_max_channel(photo_url, html_text, buttons=None):
    target_chat = MAX_CHAT_ID
    if not target_chat:
        diag_info["last_send_status"] = "❌ Ошибка: не задан MAX_CHAT_ID."
        return False

    img_payload = upload_image_to_max(photo_url)
    attachments = [{"type": "image", "payload": img_payload}]
    if buttons:
        inline_rows = [[{"type": "link", "text": b["text"], "url": b["url"]}] for b in buttons]
        attachments.append({"type": "inline_keyboard", "payload": {"buttons": inline_rows}})

    payload = {"text": html_text, "format": "html", "attachments": attachments}

    res = max_api_request("POST", "/messages", params={"chat_id": target_chat}, json_data=payload, timeout=15)
    if res:
        diag_info["last_send_status"] = f"✅ Успешно опубликовано в ID {target_chat} ({datetime.now(LOCAL_TZ).strftime('%H:%M:%S')})"
        diag_info["posts_sent_count"] += 1
        return True

    res2 = max_api_request("POST", "/messages", params={"chat_id": target_chat}, json_data={"text": html_text, "format": "html"}, timeout=15)
    if res2:
        diag_info["last_send_status"] = f"✅ Опубликовано (текст) в ID {target_chat}"
        diag_info["posts_sent_count"] += 1
        return True

    diag_info["last_send_status"] = f"❌ Ошибка API: {diag_info['last_api_debug']}"
    return False

def format_price(value):
    return f"{int(value):,}".replace(",", " ")

def pluralize_nights(n):
    if 11 <= n % 100 <= 19: return f"{n} ночей"
    rem = n % 10
    if rem == 1: return f"{n} ночь"
    if 2 <= rem <= 4: return f"{n} ночи"
    return f"{n} ночей"

def format_transfers(count):
    if count == 0: return "Прямой перелет"
    if count == 1: return "1 удобная стыковка"
    return f"{count} пересадки"

def format_human_date(d_obj):
    return f"{d_obj.day} {MONTHS_RU[d_obj.month]} ({DAYS_RU[d_obj.weekday()]})"

def fetch_flights(origin_code, one_way="false"):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {"origin": origin_code, "currency": "rub", "sorting": "price", "one_way": one_way, "limit": 100, "token": TRAVELPAYOUTS_TOKEN}
    try:
        res = session.get(url, params=params, timeout=15)
        if res.status_code == 200: return res.json().get("data", [])
    except Exception: pass
    return []

def fetch_hotel_stay_price(city_en, check_in, check_out, fallback_per_night, nights):
    url = "http://engine.hotellook.com/api/v2/cache.json"
    params = {"location": city_en, "checkIn": check_in, "checkOut": check_out, "adults": 2, "currency": "rub", "limit": 5, "token": TRAVELPAYOUTS_TOKEN}
    try:
        res = session.get(url, params=params, timeout=6)
        if res.status_code == 200:
            hotels = res.json()
            if isinstance(hotels, list) and hotels:
                prices = [h.get("priceFrom") for h in hotels if h.get("priceFrom")]
                if prices: return int(min(prices))
    except Exception: pass
    return int(fallback_per_night * nights)

def build_tour_card(d):
    is_hot = d["days_left"] <= HOT_DAYS_THRESHOLD
    if d["is_package_tour"]:
        header = "💎🔥 <b>ЭКСКЛЮЗИВНЫЙ ПАКЕТНЫЙ ТУР: СУПЕРЦЕНА!</b>" if d["discount"] >= 30 else (
            f"🔥🏖 <b>ГОРЯЩИЙ ТУР НА МОРЕ (ВЫГОДА {d['discount']}%)</b>" if is_hot else f"🌴🗓 <b>ПАКЕТНЫЙ ТУР: РАННЕЕ БРОНИРОВАНИЕ (-{d['discount']}%)</b>"
        )
        text = (
            f"{header}\n━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
            f"📅 <b>Даты тура:</b> {d['dates_human']}\n"
            f"🌙 <b>Длительность:</b> {pluralize_nights(d['nights'])}\n"
            f"🏨 <b>Проживание:</b> {d['stars']} • {d['meal']}\n"
            f"✈️ <b>Перелет:</b> Туда-обратно ({d['airline']}, {d['transfer_str']})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>За 1 человека:</b> {format_price(d['tour_price_1'])} ₽\n"
            f"👩‍❤️‍👨 <b>Полный тур на двоих: {format_price(d['tour_price_2'])} ₽</b> <s>{format_price(d['tour_avg_2'])} ₽</s>\n"
            f"💸 <b>Экономия на паре:</b> {format_price(d['saved_2'])} ₽\n"
            f"━━━━━━━━━━━━━━━━━━━\n{d['hashtags']}"
        )
        buttons = [
            {"text": f"🏖 Выбрать отель ({format_price(d['hotel_stay_2'])} ₽)", "url": d["hotel_link"]},
            {"text": f"✈️ Забрать перелет ({format_price(d['flight_price_2'])} ₽)", "url": d["flight_link_2"]},
            {"text": "📡 Радар Путешествий в MAX", "url": CHANNEL_LINK}
        ]
    else:
        text = (
            f"⚡️✈️ <b>ОБВАЛ ЦЕН НА АВИАБИЛЕТЫ (-{d['discount']}%)</b>\n━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
            f"📅 <b>Дата вылета:</b> {d['dates_human']}\n"
            f"✈️ <b>Рейс:</b> {d['airline']} • {d['transfer_str']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Билеты на двоих: {format_price(d['flight_price_2'])} ₽</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n{d['hashtags']}"
        )
        buttons = [{"text": f"🎟 Билеты на двоих — {format_price(d['flight_price_2'])} ₽", "url": d["flight_link_2"]}]
    return text, buttons

def publish_editorial_post(slot_name, force=False):
    now_local = datetime.now(LOCAL_TZ)
    log_key = f"{now_local.strftime('%Y-%m-%d')}_{slot_name}"
    if not force and bot_state["editorial_log"].get(log_key): return False

    posts_list = EDITORIAL_POSTS[slot_name]
    idx = bot_state["editorial_index"].get(slot_name, 0) % len(posts_list)
    post = posts_list[idx]

    html_text = (
        f"{post['badge']}\n━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{post['title']}</b>\n\n{post['body']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Совет Радара:</b> <i>{post['tip']}</i>\n\n{post['tags']} #радарпутешествий"
    )
    buttons = [{"text": "📡 Подписаться на Радар Путешествий", "url": CHANNEL_LINK}]

    if send_to_max_channel(post["photo"], html_text, buttons):
        bot_state["editorial_log"][log_key] = True
        bot_state["editorial_index"][slot_name] = idx + 1
        save_state(bot_state)
        return True
    return False

def run_radar_cycle():
    check_bot_identity()
    current_hour = datetime.now(LOCAL_TZ).hour
    for slot_name, target_hour in EDITORIAL_SLOTS.items():
        if current_hour == target_hour: publish_editorial_post(slot_name, force=False)

    if diag_info["posts_sent_count"] == 0:
        publish_editorial_post("morning", force=True)

    today = date.today()
    sent_set = set(bot_state["sent_deals"])
    candidates = []
    origin_items = list(ORIGINS.items())
    random.shuffle(origin_items)

    for orig_code, orig_meta in origin_items:
        all_flights = fetch_flights(orig_code, "false") + fetch_flights(orig_code, "true")
        if not all_flights: continue

        dest_prices = {}
        for f in all_flights:
            d_code = f.get("destination")
            p = f.get("price") or f.get("value")
            if d_code and p:
                dest_prices.setdefault(f"{d_code}_{'RT' if f.get('return_at') else 'OW'}", []).append(p)
        dest_avg = {k: sum(v) / len(v) for k, v in dest_prices.items()}

        for f in all_flights:
            dest_code = f.get("destination")
            flight_price_1 = f.get("price") or f.get("value")
            dep_at = f.get("departure_at", "")[:10]
            ret_at = f.get("return_at", "")[:10]
            if not flight_price_1 or not dep_at or dest_code not in CITY_DATA: continue
            try:
                dep_date = datetime.strptime(dep_at, "%Y-%m-%d").date()
                days_left = (dep_date - today).days
                if not (0 <= days_left <= MAX_DAYS_AHEAD): continue
            except ValueError: continue

            deal_id = f"{orig_code}_{dest_code}_{dep_at}_{ret_at}_{flight_price_1}"
            if deal_id in sent_set: continue

            is_rt = bool(ret_at)
            avg_flight_1 = dest_avg.get(f"{dest_code}_{'RT' if is_rt else 'OW'}", flight_price_1)
            if flight_price_1 >= avg_flight_1: continue

            dest_info = CITY_DATA[dest_code]
            ddmm_dep = dep_at[8:10] + dep_at[5:7]
            airline_code = f.get("airline", "")
            airline_name = AIRLINES.get(airline_code, "Регулярный рейс")

            if is_rt:
                try:
                    ret_date = datetime.strptime(ret_at, "%Y-%m-%d").date()
                    nights = (ret_date - dep_date).days
                    if not (5 <= nights <= 15): continue
                except ValueError: continue
                hotel_stay_2 = fetch_hotel_stay_price(dest_info["en"], dep_at, ret_at, dest_info["hotel_base_2p"], nights)
                flight_price_2 = flight_price_1 * 2
                tour_price_2 = flight_price_2 + hotel_stay_2
                tour_avg_2 = int(avg_flight_1 * 2) + int(dest_info["hotel_base_2p"] * nights * 1.18)
                discount = int((1 - (tour_price_2 / tour_avg_2)) * 100)
                if discount < MIN_TOUR_DISCOUNT: continue
                ddmm_ret = ret_at[8:10] + ret_at[5:7]
                search_route = f"{orig_code}{ddmm_dep}{dest_code}{ddmm_ret}"
                candidates.append({
                    "deal_id": deal_id, "is_package_tour": True, "priority_score": discount + 20,
                    "orig_name": orig_meta["name"], "dest_name": dest_info["name"], "photo": dest_info["photo"],
                    "dates_human": f"{format_human_date(dep_date)} – {format_human_date(ret_date)}",
                    "days_left": days_left, "nights": nights, "stars": dest_info["stars"], "meal": dest_info["meal"],
                    "airline": airline_name, "transfer_str": format_transfers(f.get("transfers", 0)),
                    "discount": discount, "tour_price_1": tour_price_2 // 2, "tour_price_2": tour_price_2,
                    "tour_avg_2": tour_avg_2, "hotel_stay_2": hotel_stay_2, "flight_price_2": flight_price_2,
                    "saved_2": tour_avg_2 - tour_price_2,
                    "hotel_link": f"https://search.hotellook.com/?destination={dest_info['en']}&checkIn={dep_at}&checkOut={ret_at}&adults=2&marker={MARKER}&language=ru",
                    "flight_link_2": f"https://www.aviasales.ru/search/{search_route}2?marker={MARKER}",
                    "hashtags": f"{orig_meta['tag']} {dest_info['tag']} #пакетныйтур #отпускподключ"
                })
        time.sleep(0.3)

    candidates.sort(key=lambda x: x["priority_score"], reverse=True)
    sent_count = 0
    used_routes = set()
    for deal in candidates:
        route_key = f"{deal['orig_name']}_{deal['dest_name']}"
        if route_key in used_routes: continue
        html_text, buttons = build_tour_card(deal)
        if send_to_max_channel(deal["photo"], html_text, buttons):
            bot_state["sent_deals"].append(deal["deal_id"])
            used_routes.add(route_key)
            sent_count += 1
            save_state(bot_state)
            time.sleep(4)
        if sent_count >= MAX_DEALS_PER_CYCLE: break

@app.route("/")
def dashboard():
    check_bot_identity()
    return f"""
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Пульт Радара Путешествий MAX</title></head>
    <body style="font-family: sans-serif; padding: 18px; background: #121212; color: #f0f0f0; line-height: 1.45;">
        <h2>📡 Пульт управления: Радар Путешествий (MAX)</h2>
        <p><b>Бот:</b> <span style="color:#4da3ff;">{diag_info['bot_profile']}</span></p>
        <p><b>Жесткий chat_id канала:</b> <code>{MAX_CHAT_ID}</code></p>
        <p><b>Статус:</b> <code>{diag_info['last_send_status']}</code></p>
        <p><b>Ответ API:</b> <code style="color:#aaa;">{diag_info['last_api_debug']}</code></p>
        <p><a href="/send_now" style="display:inline-block; padding:12px 20px; background:#2b7de9; color:#fff; text-decoration:none; border-radius:8px; font-weight:bold;">🚀 Опубликовать пост прямо сейчас</a></p>
    </body>
    </html>
    """, 200

@app.route("/send_now")
def trigger_send_now():
    Thread(target=lambda: publish_editorial_post("morning", force=True), daemon=True).start()
    time.sleep(1.5)
    return redirect("/")

def background_worker():
    while True:
        try: run_radar_cycle()
        except Exception as e: logger.error(f"Сбой: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    Thread(target=background_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
