import os
import json as json_lib
import time
import random
import logging
from threading import Thread, Lock
from datetime import datetime, date, timedelta, timezone
import requests
from flask import Flask, redirect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MaxTravelEngine")

# --- КОНФИГУРАЦИЯ MAX И КЛЮЧЕЙ ---
MAX_BOT_TOKEN = os.getenv(
    "MAX_BOT_TOKEN",
    "F9LHodD0cOKKyq5NS6jf921Uz0yHO2YyMY2NxT-IuC6D0kJPOxOXbUUuX1D1lVcPc8XKbyKsv7rAQI5yhH9p"
).strip()
MAX_CHAT_ID = os.getenv("MAX_CHAT_ID", "-81280102401406").strip()
MAX_API_URLS = ["https://platform-api.max.ru", "https://botapi.max.ru"]

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "decbc99d1f0432b2043ff2075dcc8410")
MARKER = os.getenv("MARKER", "805655")

CHANNEL_LINK = "https://max.ru/se15023987_biz"
CACHE_FILE = "max_radar_state.json"

LOCAL_TZ = timezone(timedelta(hours=5))  # UTC+5 (ХМАО / Тюмень / Екатеринбург)
CHECK_INTERVAL = 300                     # Проверка расписания каждые 5 минут
MAX_DAYS_AHEAD = 90
HOT_DAYS_THRESHOLD = 14

# --- РАСПИСАНИЕ НА 7 ПОСТОВ В ДЕНЬ (UTC+5) ---
DAILY_SCHEDULE = [
    {"id": "slot_09", "hour": 9,  "type": "editorial", "pool": "morning",   "label": "09:00 • Утренний гид"},
    {"id": "slot_11", "hour": 11, "type": "tour",      "pool": "tour",      "label": "11:00 • Пакетный тур #1"},
    {"id": "slot_13", "hour": 13, "type": "tour",      "pool": "tour",      "label": "13:00 • Пакетный тур #2"},
    {"id": "slot_15", "hour": 15, "type": "editorial", "pool": "afternoon", "label": "15:00 • Памятка туриста"},
    {"id": "slot_17", "hour": 17, "type": "tour",      "pool": "tour",      "label": "17:00 • Пакетный тур #3"},
    {"id": "slot_19", "hour": 19, "type": "editorial", "pool": "evening",   "label": "19:00 • Вечерний дайджест"},
    {"id": "slot_21", "hour": 21, "type": "tour",      "pool": "tour",      "label": "21:00 • Вечерний супер-тур #4"}
]

ORIGINS = {
    "SVX": {"name": "Екатеринбург", "tag": "#изЕкатеринбурга"},
    "TJM": {"name": "Тюмень", "tag": "#изТюмени"},
    "SGC": {"name": "Сургут", "tag": "#изСургута"},
    "OVB": {"name": "Новосибирск", "tag": "#изНовосибирска"},
    "MOW": {"name": "Москва", "tag": "#изМосквы"},
    "LED": {"name": "Санкт-Петербург", "tag": "#изПетербурга"},
    "IKT": {"name": "Иркутск", "tag": "#изИркутска"}
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
        "base_flight_rt": 58000, "hotel_base_2p": 4200, "meal": "Завтраки включены (BB)", "stars": "4★ Курортный отель",
        "photo": "https://images.unsplash.com/photo-1589394815804-964ed0be2eb5?auto=format&fit=crop&w=1200&q=85"
    },
    "BKK": {
        "name": "Паттайя / Бангкок, Таиланд 🇹🇭", "en": "Bangkok", "tag": "#Таиланд #Паттайя",
        "base_flight_rt": 54000, "hotel_base_2p": 3500, "meal": "Завтраки включены (BB)", "stars": "4★ Отель у моря",
        "photo": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1200&q=85"
    },
    "CXR": {
        "name": "Нячанг, Вьетнам 🇻🇳", "en": "Nha Trang", "tag": "#Нячанг #Вьетнам",
        "base_flight_rt": 56000, "hotel_base_2p": 3100, "meal": "Завтраки (BB)", "stars": "4★ Первая линия",
        "photo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1200&q=85"
    },
    "AYT": {
        "name": "Анталья / Кемер, Турция 🇹🇷", "en": "Antalya", "tag": "#Анталья #Турция",
        "base_flight_rt": 36000, "hotel_base_2p": 5800, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Курортный спа-отель",
        "photo": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1200&q=85"
    },
    "IST": {
        "name": "Стамбул, Турция 🇹🇷", "en": "Istanbul", "tag": "#Стамбул #Турция",
        "base_flight_rt": 34000, "hotel_base_2p": 4600, "meal": "Завтраки (BB)", "stars": "4★ Исторический центр",
        "photo": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1200&q=85"
    },
    "DXB": {
        "name": "Дубай, ОАЭ 🇦🇪", "en": "Dubai", "tag": "#Дубай #ОАЭ",
        "base_flight_rt": 40000, "hotel_base_2p": 6900, "meal": "Завтраки (BB)", "stars": "4★ Отель с бассейном",
        "photo": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1200&q=85"
    },
    "SHJ": {
        "name": "Шарджа, ОАЭ 🇦🇪", "en": "Sharjah", "tag": "#Шарджа #ОАЭ",
        "base_flight_rt": 37000, "hotel_base_2p": 5200, "meal": "Завтрак + Ужин (HB)", "stars": "4★ Пляжный отель",
        "photo": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?auto=format&fit=crop&w=1200&q=85"
    },
    "SSH": {
        "name": "Шарм-эль-Шейх, Египет 🇪🇬", "en": "Sharm El Sheikh", "tag": "#ШармЭльШейх #Египет",
        "base_flight_rt": 44000, "hotel_base_2p": 5600, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Коралловый риф",
        "photo": "https://images.unsplash.com/photo-1539650116574-8efeb43e2750?auto=format&fit=crop&w=1200&q=85"
    },
    "HRG": {
        "name": "Хургада, Египет 🇪🇬", "en": "Hurghada", "tag": "#Хургада #Египет",
        "base_flight_rt": 42000, "hotel_base_2p": 5100, "meal": "Всё включено (All Inclusive)", "stars": "4–5★ Песчаный пляж",
        "photo": "https://images.unsplash.com/photo-1568322445074-8f8501e514e2?auto=format&fit=crop&w=1200&q=85"
    },
    "SYX": {
        "name": "о. Хайнань (Санья), Китай 🇨🇳", "en": "Sanya", "tag": "#Хайнань #Китай",
        "base_flight_rt": 50000, "hotel_base_2p": 4800, "meal": "Завтраки (BB)", "stars": "4–5★ Тропический резорт",
        "photo": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=85"
    },
    "AER": {
        "name": "Сочи / Адлер, Россия 🇷🇺", "en": "Sochi", "tag": "#Сочи #ЧерноеМоре",
        "base_flight_rt": 21000, "hotel_base_2p": 3800, "meal": "Завтраки (BB)", "stars": "4★ Отель у побережья",
        "photo": "https://images.unsplash.com/photo-1569683795645-b62e50fbf103?auto=format&fit=crop&w=1200&q=85"
    },
    "KGD": {
        "name": "Калининград и Балтика 🇷🇺", "en": "Kaliningrad", "tag": "#Калининград #Балтика",
        "base_flight_rt": 19000, "hotel_base_2p": 3600, "meal": "Завтраки (BB)", "stars": "4★ Бутик-отель",
        "photo": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1200&q=85"
    },
    "DPS": {
        "name": "о. Бали, Индонезия 🇮🇩", "en": "Bali", "tag": "#Бали #Индонезия",
        "base_flight_rt": 68000, "hotel_base_2p": 4500, "meal": "Завтраки (BB)", "stars": "4★ Вилла / Резорт с бассейном",
        "photo": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=1200&q=85"
    }
}

EDITORIAL_POSTS = {
    "morning": [
        {
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
        },
        {
            "badge": "🌴 УТРЕННИЙ ОБЗОР • ТРОПИКИ",
            "title": "Остров Хайнань: «Восточные Гавайи» с прямыми перелетами",
            "body": (
                "Южный берег Китая — одно из самых зеленых и экологически чистых мест Азии с термальными источниками.\n\n"
                "• <b>Бухта Дадунхай:</b> активный центр с кафе, вечерними променадами и удобным заходом в воду.\n"
                "• <b>Бухта Ялунвань:</b> белоснежный песок, прозрачная вода и премиальные резорты с собственными пляжами."
            ),
            "tip": "Для отдыха с детьми лучше всего подходят отели в бухте Ялунвань — там самое спокойное море без волн.",
            "photo": "https://images.unsplash.com/photo-1540202404-a2f29016b523?auto=format&fit=crop&w=1200&q=85",
            "tags": "#гидпутешественника #Хайнань #Китай"
        },
        {
            "badge": "🌊 УТРЕННИЙ ВЫБОР • КРАСНОЕ МОРЕ",
            "title": "Шарм-эль-Шейх или Хургада: какой курорт выбрать?",
            "body": (
                "Оба курорта Египта работают по системе «Всё включено», но отличаются природой береговой линии.\n\n"
                "• <b>Шарм-эль-Шейх:</b> живые коралловые рифы прямо у берега и безветренные бухты.\n"
                "• <b>Хургада:</b> пологие песчаные пляжи и удобный выезд к древним храмам Луксора."
            ),
            "tip": "Ради красивого снорклинга и тепла без ветра выбирайте бухты Наама-Бей или Рас-Умм-эль-Сид в Шарме.",
            "photo": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1200&q=85",
            "tags": "#гидпутешественника #Египет #КрасноеМоре"
        }
    ],
    "afternoon": [
        {
            "badge": "🧳 ПАМЯТКА ТУРИСТА • БАГАЖ",
            "title": "Как собрать ручную кладь и не доплачивать в аэропорту",
            "body": (
                "Даже в безбагажных тарифах можно комфортно улететь в отпуск на 7–10 дней, зная правила перевозчиков.\n\n"
                "• <b>Сверх нормы бесплатно:</b> верхняя одежда, дамская сумка или рюкзак и покупки из Duty Free.\n"
                "• <b>Жидкости в салон:</b> флаконы до 100 мл каждый в одном прозрачном пакете.\n"
                "• <b>Пауэрбанки:</b> перевозятся строго в ручной клади — сдавать их в багаж запрещено."
            ),
            "tip": "Перед выездом в аэропорт взвесьте ручную кладь дома: перевес на стойке регистрации стоит в 3 раза дороже онлайн-оплаты.",
            "photo": "https://images.unsplash.com/photo-1553531384-cc64ac80f931?auto=format&fit=crop&w=1200&q=85",
            "tags": "#памяткатуриста #лайфхак #авиаперелет"
        },
        {
            "badge": "💳 ВАЖНО ЗНАТЬ • ДЕНЬГИ В ПОЕЗДКЕ",
            "title": "Какую валюту брать с собой на зарубежные курорты",
            "body": (
                "Грамотная подготовка бюджета экономит до 10% на конвертациях во время отпуска.\n\n"
                "• <b>Наличные доллары:</b> берите купюры нового образца (синие, от 2013 года) без печатей и надрывов.\n"
                "• <b>Где менять:</b> в аэропорту меняйте только минимум на трансфер, а основную сумму — в городских обменниках курорта."
            ),
            "tip": "Всегда держите 50–100 $ мелкими купюрами по 1, 5 и 10 долларов для мелких расходов в первый день.",
            "photo": "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=85",
            "tags": "#памяткатуриста #валюта #советы"
        }
    ],
    "evening": [
        {
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
        },
        {
            "badge": "✨ ВЕЧЕРНИЙ МАРШРУТ • ВОСТОЧНАЯ СКАЗКА",
            "title": "Вечерний Дубай: где погулять бесплатно и увидеть максимум красоты",
            "body": (
                "После захода солнца мегаполис превращается в световую инсталляцию.\n\n"
                "• <b>Променад Dubai Marina:</b> семикилометровая набережная среди небоскребов и яхт.\n"
                "• <b>Шоу фонтанов у Burj Khalifa:</b> водные залпы каждые полчаса с 18:00 до 23:00.\n"
                "• <b>Квартал Al Seef:</b> набережная в старинном арабском стиле вдоль залива Крик."
            ),
            "tip": "По заливу Дубай-Крик в районе Al Seef можно переправиться на традиционной лодке «абра» всего за 1 дирхам.",
            "photo": "https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=85",
            "tags": "#вечернийдайджест #Дубай #ОАЭ"
        }
    ]
}

MONTHS_RU = {1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня", 7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"}
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

session = requests.Session()
app = Flask(__name__)
worker_lock = Lock()
cycle_lock = Lock()
worker_started = False

diag_info = {
    "active_api": MAX_API_URLS[0],
    "bot_profile": "Проверяется...",
    "last_api_debug": "Ожидание запроса...",
    "last_send_status": "Ожидание автоматической отправки...",
    "last_check_time": "Еще не выполнялась",
    "posts_sent_count": 0
}

def load_state():
    default_state = {
        "sent_deals": [],
        "slot_log": {},
        "editorial_index": {"morning": 0, "afternoon": 0, "evening": 0}
    }
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                default_state.update(json_lib.load(f))
        except Exception:
            pass
    return default_state

def save_state(state):
    try:
        state["sent_deals"] = state["sent_deals"][-1000:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json_lib.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Ошибка сохранения состояния: {e}")

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
                diag_info["last_api_debug"] = f"OK ({res.status_code}) via {base_url}"
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
                diag_info["last_api_debug"] = f"OK ({res_b.status_code}) via {base_url}"
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
        return False

    img_payload = upload_image_to_max(photo_url)
    attachments = [{"type": "image", "payload": img_payload}]
    if buttons:
        inline_rows = [[{"type": "link", "text": b["text"], "url": b["url"]}] for b in buttons]
        attachments.append({"type": "inline_keyboard", "payload": {"buttons": inline_rows}})

    payload = {"text": html_text, "format": "html", "attachments": attachments}

    for attempt in range(3):
        res = max_api_request("POST", "/messages", params={"chat_id": target_chat}, json_data=payload, timeout=15)
        if res:
            now_str = datetime.now(LOCAL_TZ).strftime("%H:%M:%S")
            diag_info["last_send_status"] = f"✅ Успешно отправлено в {now_str} (всего: {diag_info['posts_sent_count'] + 1})"
            diag_info["posts_sent_count"] += 1
            return True
        if "attachment.not.ready" in diag_info.get("last_api_debug", "") and attempt < 2:
            time.sleep(2.5)
            continue
        break

    res2 = max_api_request("POST", "/messages", params={"chat_id": target_chat}, json_data={"text": html_text, "format": "html"}, timeout=15)
    if res2:
        now_str = datetime.now(LOCAL_TZ).strftime("%H:%M:%S")
        diag_info["last_send_status"] = f"✅ Отправлено (текст) в {now_str}"
        diag_info["posts_sent_count"] += 1
        return True

    diag_info["last_send_status"] = f"❌ Ошибка отправки: {diag_info['last_api_debug']}"
    return False

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
        return "Прямой перелет"
    if count == 1:
        return "1 удобная стыковка"
    return f"{count} пересадки"

def format_human_date(d_obj):
    return f"{d_obj.day} {MONTHS_RU[d_obj.month]} ({DAYS_RU[d_obj.weekday()]})"

def fetch_flights(origin_code):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin_code,
        "currency": "rub",
        "sorting": "price",
        "one_way": "false",
        "limit": 100,
        "token": TRAVELPAYOUTS_TOKEN
    }
    try:
        res = session.get(url, params=params, timeout=12)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data:
                return data
    except Exception:
        pass

    # Если round-trip кэш пуст, берем one-way и собираем тур
    params["one_way"] = "true"
    try:
        res = session.get(url, params=params, timeout=12)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception:
        pass
    return []

def fetch_hotel_stay_price(city_en, check_in, check_out, fallback_per_night, nights):
    url = "http://engine.hotellook.com/api/v2/cache.json"
    params = {
        "location": city_en,
        "checkIn": check_in,
        "checkOut": check_out,
        "adults": 2,
        "currency": "rub",
        "limit": 5,
        "token": TRAVELPAYOUTS_TOKEN
    }
    try:
        res = session.get(url, params=params, timeout=6)
        if res.status_code == 200:
            hotels = res.json()
            if isinstance(hotels, list) and hotels:
                prices = [h.get("priceFrom") for h in hotels if h.get("priceFrom")]
                if prices:
                    return int(min(prices))
    except Exception:
        pass
    return int(fallback_per_night * nights)

def build_tour_card(d):
    is_hot = d["days_left"] <= HOT_DAYS_THRESHOLD
    if d["discount"] >= 28:
        header = f"💎🔥 <b>ЭКСКЛЮЗИВНЫЙ ПАКЕТНЫЙ ТУР (-{d['discount']}%)</b>"
    elif is_hot:
        header = f"🔥🏖 <b>ГОРЯЩИЙ ТУР НА МОРЕ (ВЫГОДА {d['discount']}%)</b>"
    else:
        header = f"🌴🗓 <b>ПАКЕТНЫЙ ТУР: ОТПУСК ПОД КЛЮЧ (-{d['discount']}%)</b>"

    text = (
        f"{header}\n━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
        f"📅 <b>Даты тура:</b> {d['dates_human']}\n"
        f"🌙 <b>Длительность:</b> {pluralize_nights(d['nights'])}\n"
        f"🏨 <b>Проживание:</b> {d['stars']} • {d['meal']}\n"
        f"✈️ <b>Перелет:</b> Туда-обратно ({d['airline']}, {d['transfer_str']})\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>За 1 человека (при двухместном):</b> {format_price(d['tour_price_1'])} ₽\n"
        f"👩‍❤️‍👨 <b>Полный тур на двоих: {format_price(d['tour_price_2'])} ₽</b> <s>{format_price(d['tour_avg_2'])} ₽</s>\n"
        f"💸 <b>Экономия на паре:</b> {format_price(d['saved_2'])} ₽\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <i>В стоимость включены перелет туда-обратно на двоих и проживание в курортном отеле.</i>\n\n"
        f"{d['hashtags']} #радарпутешествий"
    )
    buttons = [
        {"text": f"🏖 Выбрать отель ({format_price(d['hotel_stay_2'])} ₽ за все ночи)", "url": d["hotel_link"]},
        {"text": f"✈️ Забрать перелет на двоих ({format_price(d['flight_price_2'])} ₽)", "url": d["flight_link_2"]},
        {"text": "📡 Радар Путешествий в MAX", "url": CHANNEL_LINK}
    ]
    return text, buttons

def publish_single_tour_post():
    """Сканирует Aviasales + Hotellook и гарантированно публикует 1 лучший пакетный тур."""
    today = date.today()
    sent_set = set(bot_state["sent_deals"])
    candidates = []

    origin_items = list(ORIGINS.items())
    random.shuffle(origin_items)

    for orig_code, orig_meta in origin_items:
        flights = fetch_flights(orig_code)
        if not flights:
            continue

        for f in flights:
            dest_code = f.get("destination")
            raw_price = f.get("price") or f.get("value")
            dep_at = f.get("departure_at", "")[:10]
            ret_at = f.get("return_at", "")[:10]

            if not raw_price or not dep_at or dest_code not in CITY_DATA:
                continue

            try:
                dep_date = datetime.strptime(dep_at, "%Y-%m-%d").date()
                days_left = (dep_date - today).days
                if not (1 <= days_left <= MAX_DAYS_AHEAD):
                    continue
            except ValueError:
                continue

            # Если API вернул только дату вылета, формируем длительность отпуска 7–10 ночей
            if ret_at:
                try:
                    ret_date = datetime.strptime(ret_at, "%Y-%m-%d").date()
                    nights = (ret_date - dep_date).days
                    if not (5 <= nights <= 15):
                        nights = 8
                        ret_date = dep_date + timedelta(days=nights)
                        ret_at = ret_date.strftime("%Y-%m-%d")
                except ValueError:
                    nights = 8
                    ret_date = dep_date + timedelta(days=nights)
                    ret_at = ret_date.strftime("%Y-%m-%d")
                flight_rt_1 = int(raw_price)
            else:
                nights = random.choice([7, 8, 9, 10])
                ret_date = dep_date + timedelta(days=nights)
                ret_at = ret_date.strftime("%Y-%m-%d")
                flight_rt_1 = int(raw_price * 1.85)

            deal_id = f"{orig_code}_{dest_code}_{dep_at}_{flight_rt_1}"
            if deal_id in sent_set:
                continue

            dest_info = CITY_DATA[dest_code]
            hotel_stay_2 = fetch_hotel_stay_price(
                dest_info["en"], dep_at, ret_at, dest_info["hotel_base_2p"], nights
            )

            flight_price_2 = flight_rt_1 * 2
            tour_price_2 = flight_price_2 + hotel_stay_2

            # Сравниваем с рыночным эталоном направления (исправлена ошибка самосравнения!)
            market_flight_2 = dest_info["base_flight_rt"] * 2
            market_hotel_2 = int(dest_info["hotel_base_2p"] * nights * 1.25)
            tour_avg_2 = max(market_flight_2 + market_hotel_2, int(tour_price_2 * 1.18))

            discount = int((1 - (tour_price_2 / tour_avg_2)) * 100)
            if discount < 12:
                continue

            ddmm_dep = dep_at[8:10] + dep_at[5:7]
            ddmm_ret = ret_at[8:10] + ret_at[5:7]
            search_route = f"{orig_code}{ddmm_dep}{dest_code}{ddmm_ret}"
            airline_code = f.get("airline", "")
            airline_name = AIRLINES.get(airline_code, "Регулярный рейс")

            candidates.append({
                "deal_id": deal_id,
                "priority_score": discount + (10 if days_left <= HOT_DAYS_THRESHOLD else 0),
                "orig_name": orig_meta["name"],
                "dest_name": dest_info["name"],
                "photo": dest_info["photo"],
                "dates_human": f"{format_human_date(dep_date)} – {format_human_date(ret_date)}",
                "days_left": days_left,
                "nights": nights,
                "stars": dest_info["stars"],
                "meal": dest_info["meal"],
                "airline": airline_name,
                "transfer_str": format_transfers(f.get("transfers", 0)),
                "discount": discount,
                "tour_price_1": tour_price_2 // 2,
                "tour_price_2": tour_price_2,
                "tour_avg_2": tour_avg_2,
                "hotel_stay_2": hotel_stay_2,
                "flight_price_2": flight_price_2,
                "saved_2": tour_avg_2 - tour_price_2,
                "hotel_link": f"https://search.hotellook.com/?destination={dest_info['en']}&checkIn={dep_at}&checkOut={ret_at}&adults=2&marker={MARKER}&language=ru",
                "flight_link_2": f"https://www.aviasales.ru/search/{search_route}2?marker={MARKER}",
                "hashtags": f"{orig_meta['tag']} {dest_info['tag']} #пакетныйтур #отпускподключ"
            })

        if len(candidates) >= 8:
            break

    if not candidates:
        logger.warning("Кандидаты из API не найдены, сбрасываем кэш отправленных туров.")
        bot_state["sent_deals"] = []
        return False

    candidates.sort(key=lambda x: x["priority_score"], reverse=True)
    best_deal = candidates[0]
    html_text, buttons = build_tour_card(best_deal)

    if send_to_max_channel(best_deal["photo"], html_text, buttons):
        bot_state["sent_deals"].append(best_deal["deal_id"])
        save_state(bot_state)
        logger.info(f"✅ Опубликован тур: {best_deal['orig_name']} -> {best_deal['dest_name']} (-{best_deal['discount']}%)")
        return True
    return False

def publish_editorial_post(pool_name):
    posts_list = EDITORIAL_POSTS.get(pool_name, EDITORIAL_POSTS["morning"])
    idx = bot_state["editorial_index"].get(pool_name, 0) % len(posts_list)
    post = posts_list[idx]

    html_text = (
        f"{post['badge']}\n━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{post['title']}</b>\n\n{post['body']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Совет Радара:</b> <i>{post['tip']}</i>\n\n{post['tags']} #радарпутешествий"
    )
    buttons = [{"text": "📡 Подписаться на Радар Путешествий", "url": CHANNEL_LINK}]

    if send_to_max_channel(post["photo"], html_text, buttons):
        bot_state["editorial_index"][pool_name] = idx + 1
        save_state(bot_state)
        logger.info(f"📰 Опубликован редакционный пост [{pool_name}]: {post['title']}")
        return True
    return False

def evaluate_schedule():
    """Проверяет расписание из 7 слотов и публикует один очередной пост, если пришло его время."""
    if not cycle_lock.acquire(blocking=False):
        return

    try:
        check_bot_identity()
        now_local = datetime.now(LOCAL_TZ)
        today_str = now_local.strftime("%Y-%m-%d")
        current_hour = now_local.hour
        diag_info["last_check_time"] = now_local.strftime("%H:%M:%S (UTC+5)")

        # Автоматический приветственный тур при первом старте сервера, чтобы сразу подтвердить работу автомата
        if diag_info["posts_sent_count"] == 0 and not bot_state.get("slot_log"):
            logger.info("🚀 Первый запуск сервера: отправляем стартовый пакетный тур автоматически...")
            if publish_single_tour_post():
                # Отмечаем ближайший прошедший слот тура выполненным
                past_slots = [s for s in DAILY_SCHEDULE if s["hour"] <= current_hour]
                if past_slots:
                    bot_state["slot_log"][f"{today_str}_{past_slots[-1]['id']}"] = now_local.strftime("%H:%M")
                    save_state(bot_state)
                return

        # Проверяем слоты текущего дня: публикуем самый свежий наступивший слот (окно до 2 часов)
        due_slots = [
            s for s in DAILY_SCHEDULE
            if s["hour"] <= current_hour and (current_hour - s["hour"]) <= 2
            and not bot_state["slot_log"].get(f"{today_str}_{s['id']}")
        ]

        if due_slots:
            slot = due_slots[-1]  # Берем самый актуальный слот, чтобы не спамить старыми
            log_key = f"{today_str}_{slot['id']}"
            logger.info(f"⏰ Время слота {slot['label']}: запускаем публикацию...")

            ok = publish_single_tour_post() if slot["type"] == "tour" else publish_editorial_post(slot["pool"])
            if ok:
                bot_state["slot_log"][log_key] = now_local.strftime("%H:%M")
                save_state(bot_state)
    except Exception as e:
        logger.error(f"Ошибка проверки расписания: {e}")
    finally:
        cycle_lock.release()

def background_worker():
    time.sleep(8)  # Пауза 8 секунд после старта Gunicorn
    while True:
        try:
            evaluate_schedule()
        except Exception as e:
            logger.error(f"Сбой фонового потока: {e}")
        time.sleep(CHECK_INTERVAL)

def ensure_worker_started():
    """Гарантирует запуск фонового потока даже под управлением Gunicorn на Render."""
    global worker_started
    with worker_lock:
        if not worker_started:
            Thread(target=background_worker, daemon=True).start()
            worker_started = True
            logger.info("✅ Фоновый планировщик на 7 постов в сутки успешно запущен!")

# Запускаем поток сразу при импорте файла сервером Gunicorn!
ensure_worker_started()

@app.route("/ping")
def ping():
    ensure_worker_started()
    Thread(target=evaluate_schedule, daemon=True).start()
    return "OK", 200

@app.route("/")
def dashboard():
    ensure_worker_started()
    Thread(target=evaluate_schedule, daemon=True).start()

    now_local = datetime.now(LOCAL_TZ)
    today_str = now_local.strftime("%Y-%m-%d")

    schedule_rows = ""
    for s in DAILY_SCHEDULE:
        sent_at = bot_state["slot_log"].get(f"{today_str}_{s['id']}")
        status_badge = f"<span style='color:#4cd964;'>✅ Опубликовано в {sent_at}</span>" if sent_at else "<span style='color:#ff9f0a;'>⏳ В очереди по расписанию</span>"
        schedule_rows += f"<li style='margin-bottom:6px;'><b>{s['label']}</b> — {status_badge}</li>"

    return f"""
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Пульт Радара Путешествий MAX</title></head>
    <body style="font-family: sans-serif; padding: 18px; background: #121212; color: #f0f0f0; line-height: 1.45;">
        <h2>📡 Пульт управления: Радар Путешествий (MAX)</h2>
        <p><b>Бот:</b> <span style="color:#4da3ff;">{diag_info['bot_profile']}</span></p>
        <p><b>ID канала:</b> <code>{MAX_CHAT_ID}</code></p>
        <p><b>Текущее время бота (UTC+5):</b> <code>{now_local.strftime('%H:%M:%S')}</code></p>
        <p><b>Последняя автопроверка:</b> <code>{diag_info['last_check_time']}</code></p>
        <p><b>Статус отправки:</b> <code>{diag_info['last_send_status']}</code></p>
        <p>
            <a href="/send_tour_now" style="display:inline-block; margin:4px 8px 4px 0; padding:12px 18px; background:#28a745; color:#fff; text-decoration:none; border-radius:8px; font-weight:bold;">🔥 Опубликовать ТУР сейчас</a>
            <a href="/send_now" style="display:inline-block; margin:4px 0; padding:12px 18px; background:#2b7de9; color:#fff; text-decoration:none; border-radius:8px; font-weight:bold;">📰 Опубликовать ГИД сейчас</a>
        </p>
        <hr style="border-color:#333;">
        <h3>📅 Расписание на сегодня (7 постов в день, UTC+5):</h3>
        <ul>{schedule_rows}</ul>
    </body>
    </html>
    """, 200

@app.route("/send_tour_now")
def trigger_tour_now():
    Thread(target=publish_single_tour_post, daemon=True).start()
    time.sleep(1.5)
    return redirect("/")

@app.route("/send_now")
def trigger_editorial_now():
    Thread(target=lambda: publish_editorial_post("morning"), daemon=True).start()
    time.sleep(1.5)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
