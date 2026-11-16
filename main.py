import os
import json
import time
import random
import logging
from threading import Thread
from datetime import datetime, date, timedelta, timezone
import requests
from flask import Flask, redirect

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MaxTravelEngine")

# --- КОНФИГУРАЦИЯ МЕССЕНДЖЕРА MAX И КЛЮЧЕЙ ---
MAX_BOT_TOKEN = os.getenv(
    "MAX_BOT_TOKEN",
    "F9LHodD0cOLdtWyEzXzapwvtDXuI5ZMuw2xgW3QYS4rJB1PuFKtB41AvUxhR200ADiAAoVXob03ZN6IgLkWT"
).strip()

MAX_CHAT_ID = os.getenv("MAX_CHAT_ID", "").strip()
MAX_API_URLS = ["https://botapi.max.ru", "https://platform-api.max.ru"]

TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "decbc99d1f0432b2043ff2075dcc8410")
MARKER = os.getenv("MARKER", "805655")

# Новая официальная ссылка на ваш бизнес-канал в MAX
CHANNEL_LINK = "https://max.ru/se15023987_biz"
CACHE_FILE = "max_radar_state.json"

# --- НАСТРОЙКИ РАСПИСАНИЯ И ФИЛЬТРОВ ---
LOCAL_TZ = timezone(timedelta(hours=5))  # UTC+5
SCAN_INTERVAL = 2400                     # 40 минут
MAX_DEALS_PER_CYCLE = 3
MAX_DAYS_AHEAD = 90
HOT_DAYS_THRESHOLD = 14
MIN_TOUR_DISCOUNT = 14
MIN_FLIGHT_DISCOUNT = 25

EDITORIAL_SLOTS = {
    "morning": 9,     # 09:00–09:59
    "afternoon": 14,  # 14:00–14:59
    "evening": 19     # 19:00–19:59
}

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
        },
        {
            "id": "m_hainan_guide",
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
            "id": "m_red_sea",
            "badge": "🌊 УТРЕННИЙ ВЫБОР • КРАСНОЕ МОРЕ",
            "title": "Шарм-эль-Шейх или Хургада: какой курорт выбрать?",
            "body": (
                "Оба курорта Египта работают по системе «Всё включено», но отличаются природой береговой линии.\n\n"
                "• <b>Шарм-эль-Шейх:</b> живые коралловые рифы прямо у берега и безветренные бухты (Наама-Бей, Шаркс-Бей).\n"
                "• <b>Хургада:</b> пологие песчаные пляжи и удобный выезд к древним храмам Луксора."
            ),
            "tip": "Ради красивого снорклинга и тепла без ветра выбирайте бухты Наама-Бей или Рас-Умм-эль-Сид в Шарме.",
            "photo": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1200&q=85",
            "tags": "#гидпутешественника #Египет #КрасноеМоре"
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
        },
        {
            "id": "a_currency_tips",
            "badge": "💳 ВАЖНО ЗНАТЬ • ДЕНЬГИ В ПОЕЗДКЕ",
            "title": "Какую валюту брать с собой на зарубежные курорты",
            "body": (
                "Грамотная подготовка бюджета экономит до 10% на конвертациях во время отпуска.\n\n"
                "• <b>Наличные доллары:</b> берите купюры нового образца (синие, от 2013 года) без печатей и надрывов.\n"
                "• <b>Где менять:</b> в аэропорту меняйте только минимум на такси, а основную сумму — в городских обменных пунктах курорта."
            ),
            "tip": "Всегда держите 50–100 $ мелкими купюрами по 1, 5 и 10 долларов для мелких расходов в первый день.",
            "photo": "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=1200&q=85",
            "tags": "#памяткатуриста #валюта #советы"
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
        },
        {
            "id": "e_dubai_evening",
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

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

session = requests.Session()
app = Flask(__name__)

# Диагностический журнал для просмотра прямо с телефона
diag_info = {
    "active_api": MAX_API_URLS[0],
    "found_chats": [],
    "selected_chat_id": None,
    "selected_chat_title": None,
    "last_send_status": "Ожидание первой отправки...",
    "posts_sent_count": 0
}

def load_state():
    default_state = {
        "sent_deals": [],
        "editorial_log": {},
        "editorial_index": {"morning": 0, "afternoon": 0, "evening": 0}
    }
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                default_state.update(json.load(f))
        except Exception:
            pass
    return default_state

def save_state(state):
    try:
        state["sent_deals"] = state["sent_deals"][-1500:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Ошибка сохранения состояния: {e}")

bot_state = load_state()

# --- ПОИСК АКТИВНОГО КАНАЛА В MAX API ---
def discover_target_chat(force_refresh=False):
    if MAX_CHAT_ID:
        diag_info["selected_chat_id"] = MAX_CHAT_ID
        return MAX_CHAT_ID

    if diag_info["selected_chat_id"] and not force_refresh:
        return diag_info["selected_chat_id"]

    headers = {"Authorization": MAX_BOT_TOKEN}
    params = {"access_token": MAX_BOT_TOKEN, "count": 50}

    for base_url in MAX_API_URLS:
        try:
            res = session.get(f"{base_url}/chats", headers=headers, params=params, timeout=12)
            if res.status_code == 200:
                diag_info["active_api"] = base_url
                chats = res.json().get("chats", [])
                diag_info["found_chats"] = [
                    {
                        "chat_id": c.get("chat_id"),
                        "title": c.get("title"),
                        "type": c.get("type"),
                        "status": c.get("status")
                    }
                    for c in chats
                ]

                # Сначала ищем активный канал с названием "Радар"
                active_channels = [
                    c for c in chats
                    if c.get("status") in ("active", None) and c.get("type") in ("channel", "chat")
                ]
                for c in active_channels:
                    title = (c.get("title") or "").lower()
                    if "радар" in title or "горящие" in title:
                        cid = str(c.get("chat_id"))
                        diag_info["selected_chat_id"] = cid
                        diag_info["selected_chat_title"] = c.get("title")
                        logger.info(f"🎯 Найден целевой канал MAX: '{c.get('title')}' (ID: {cid})")
                        return cid

                # Иначе берем самый свежий активный канал
                for c in active_channels:
                    if c.get("type") == "channel":
                        cid = str(c.get("chat_id"))
                        diag_info["selected_chat_id"] = cid
                        diag_info["selected_chat_title"] = c.get("title")
                        logger.info(f"🎯 Выбран активный канал MAX: '{c.get('title')}' (ID: {cid})")
                        return cid

                if active_channels:
                    cid = str(active_channels[0].get("chat_id"))
                    diag_info["selected_chat_id"] = cid
                    diag_info["selected_chat_title"] = active_channels[0].get("title")
                    return cid

                diag_info["last_send_status"] = "Список чатов пуст. Проверьте, что именно этот бот добавлен в администраторы канала."
        except Exception as e:
            diag_info["last_send_status"] = f"Ошибка /chats ({base_url}): {e}"
            logger.error(diag_info["last_send_status"])

    return None

def upload_image_to_max(photo_url):
    base_url = diag_info["active_api"]
    headers = {"Authorization": MAX_BOT_TOKEN}
    params = {"access_token": MAX_BOT_TOKEN, "type": "image"}
    try:
        up_init = session.post(f"{base_url}/uploads", headers=headers, params=params, timeout=10)
        if up_init.status_code == 200:
            upload_url = up_init.json().get("url")
            if upload_url:
                img_resp = session.get(photo_url, timeout=12)
                if img_resp.status_code == 200:
                    files = {"data": ("cover.jpg", img_resp.content, "image/jpeg")}
                    up_done = session.post(upload_url, files=files, timeout=20)
                    if up_done.status_code == 200:
                        # Даем серверу MAX 2 секунды на обработку загруженного фото
                        time.sleep(2.0)
                        return up_done.json()
    except Exception as e:
        logger.warning(f"Ошибка загрузки фото через /uploads: {e}")
    return {"url": photo_url}

def send_to_max_channel(photo_url, html_text, buttons=None):
    target_chat = discover_target_chat(force_refresh=False)
    if not target_chat:
        target_chat = discover_target_chat(force_refresh=True)
    if not target_chat:
        return False

    base_url = diag_info["active_api"]
    url = f"{base_url}/messages"
    headers = {"Authorization": MAX_BOT_TOKEN}
    params = {"access_token": MAX_BOT_TOKEN, "chat_id": target_chat}

    img_payload = upload_image_to_max(photo_url)
    attachments = [{"type": "image", "payload": img_payload}]

    if buttons:
        inline_rows = [[{"type": "link", "text": b["text"], "url": b["url"]}] for b in buttons]
        attachments.append({"type": "inline_keyboard", "payload": {"buttons": inline_rows}})

    payload = {
        "text": html_text,
        "format": "html",
        "attachments": attachments
    }

    # Попытка 1: Полная карточка с загруженным фото и кнопками (с повтором при attachment.not.ready)
    for attempt in range(3):
        try:
            res = session.post(url, headers=headers, params=params, json=payload, timeout=15)
            if res.status_code in (200, 201):
                diag_info["last_send_status"] = f"Успешно отправлено в {diag_info['selected_chat_title']} ({datetime.now(LOCAL_TZ).strftime('%H:%M:%S')})"
                diag_info["posts_sent_count"] += 1
                return True
            if "attachment.not.ready" in res.text and attempt < 2:
                time.sleep(2.5)
                continue
            diag_info["last_send_status"] = f"Ответ MAX ({res.status_code}): {res.text}"
            logger.warning(diag_info["last_send_status"])
            break
        except Exception as e:
            diag_info["last_send_status"] = f"Ошибка соединения: {e}"
            break

    # Попытка 2: Если чат устарел (404/403), обновляем список каналов, а если ошибка во вложении — шлем текст с кнопками
    discover_target_chat(force_refresh=True)
    fallback_attachments = []
    if buttons:
        inline_rows = [[{"type": "link", "text": b["text"], "url": b["url"]}] for b in buttons]
        fallback_attachments.append({"type": "inline_keyboard", "payload": {"buttons": inline_rows}})

    fallback_payload = {
        "text": html_text,
        "format": "html",
        "attachments": fallback_attachments
    }
    try:
        res2 = session.post(url, headers=headers, params=params, json=fallback_payload, timeout=15)
        if res2.status_code in (200, 201):
            diag_info["last_send_status"] = f"Отправлено (без фото) в {diag_info['selected_chat_title']}"
            diag_info["posts_sent_count"] += 1
            return True
    except Exception:
        pass

    return False

# --- ФОРМАТИРОВАНИЕ ---
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
    elif count == 1:
        return "1 удобная стыковка"
    return f"{count} пересадки"

def format_human_date(d_obj):
    return f"{d_obj.day} {MONTHS_RU[d_obj.month]} ({DAYS_RU[d_obj.weekday()]})"

def fetch_flights(origin_code, one_way="false"):
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin_code,
        "currency": "rub",
        "sorting": "price",
        "one_way": one_way,
        "limit": 100,
        "token": TRAVELPAYOUTS_TOKEN
    }
    try:
        res = session.get(url, params=params, timeout=15)
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception as e:
        logger.error(f"Ошибка API перелетов ({origin_code}): {e}")
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

    if d["is_package_tour"]:
        if d["discount"] >= 30:
            header = "💎🔥 <b>ЭКСКЛЮЗИВНЫЙ ПАКЕТНЫЙ ТУР: СУПЕРЦЕНА!</b>"
        elif is_hot:
            header = f"🔥🏖 <b>ГОРЯЩИЙ ТУР НА МОРЕ (ВЫГОДА {d['discount']}%)</b>"
        else:
            header = f"🌴🗓 <b>ПАКЕТНЫЙ ТУР: РАННЕЕ БРОНИРОВАНИЕ (-{d['discount']}%)</b>"

        text = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
            f"📅 <b>Даты тура:</b> {d['dates_human']}\n"
            f"🌙 <b>Длительность:</b> {pluralize_nights(d['nights'])}\n"
            f"🏨 <b>Проживание:</b> {d['stars']} • {d['meal']}\n"
            f"✈️ <b>Перелет:</b> Туда-обратно ({d['airline']}, {d['transfer_str']})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>За 1 человека (при двухместном):</b> {format_price(d['tour_price_1'])} ₽\n"
            f"👩‍❤️‍👨 <b>Полный тур на двоих: {format_price(d['tour_price_2'])} ₽</b> <s>{format_price(d['tour_avg_2'])} ₽</s>\n"
            f"💸 <b>Ваша экономия на паре:</b> {format_price(d['saved_2'])} ₽\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>В расчет включены перелет туда-обратно на двоих и проживание в курортном отеле.</i>\n\n"
            f"{d['hashtags']}"
        )

        buttons = [
            {"text": f"🏖 Выбрать отель ({format_price(d['hotel_stay_2'])} ₽ за все ночи)", "url": d["hotel_link"]},
            {"text": f"✈️ Забрать перелет на двоих ({format_price(d['flight_price_2'])} ₽)", "url": d["flight_link_2"]},
            {"text": "📡 Радар Путешествий в MAX", "url": CHANNEL_LINK}
        ]
    else:
        header = f"⚡️✈️ <b>РЕДКИЙ ОБВАЛ ЦЕН НА АВИАБИЛЕТЫ (-{d['discount']}%)</b>"
        text = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>{d['orig_name']} ➔ {d['dest_name']}</b>\n\n"
            f"📅 <b>Дата вылета:</b> {d['dates_human']}\n"
            f"✈️ <b>Рейс:</b> {d['airline']} • {d['transfer_str']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Билет на одного:</b> {format_price(d['flight_price_1'])} ₽ <s>{format_price(d['flight_avg_1'])} ₽</s>\n"
            f"👥 <b>Билеты на двоих: {format_price(d['flight_price_2'])} ₽</b> <i>(выгода {format_price(d['saved_2'])} ₽)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔥 <i>Эксклюзивный тариф для самостоятельного путешествия!</i>\n\n"
            f"{d['hashtags']}"
        )

        buttons = [
            {"text": f"🎟 Билет на 1 чел. — {format_price(d['flight_price_1'])} ₽", "url": d["flight_link_1"]},
            {"text": f"👩‍❤️‍👨 Билеты на двоих — {format_price(d['flight_price_2'])} ₽", "url": d["flight_link_2"]}
        ]

    return text, buttons

def publish_editorial_post(slot_name, force=False):
    now_local = datetime.now(LOCAL_TZ)
    today_str = now_local.strftime("%Y-%m-%d")
    log_key = f"{today_str}_{slot_name}"

    if not force and bot_state["editorial_log"].get(log_key):
        return False

    posts_list = EDITORIAL_POSTS[slot_name]
    idx = bot_state["editorial_index"].get(slot_name, 0) % len(posts_list)
    post = posts_list[idx]

    html_text = (
        f"{post['badge']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{post['title']}</b>\n\n"
        f"{post['body']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Совет Радара:</b> <i>{post['tip']}</i>\n\n"
        f"{post['tags']} #радарпутешествий"
    )
    buttons = [{"text": "📡 Подписаться на Радар Путешествий", "url": CHANNEL_LINK}]

    if send_to_max_channel(post["photo"], html_text, buttons):
        bot_state["editorial_log"][log_key] = True
        bot_state["editorial_index"][slot_name] = idx + 1
        save_state(bot_state)
        logger.info(f"📰 Опубликован редакционный пост [{slot_name}]: {post['title']}")
        return True
    return False

def check_and_publish_editorial():
    current_hour = datetime.now(LOCAL_TZ).hour
    for slot_name, target_hour in EDITORIAL_SLOTS.items():
        if current_hour == target_hour:
            publish_editorial_post(slot_name, force=False)

def run_radar_cycle():
    discover_target_chat(force_refresh=True)
    check_and_publish_editorial()

    # Если за всё время работы еще не отправлено ни одного поста — сразу шлем приветственный утренний гид для проверки канала!
    if diag_info["posts_sent_count"] == 0:
        publish_editorial_post("morning", force=True)

    logger.info("📡 Сканирование пакетных туров и эксклюзивных перелетов...")
    today = date.today()
    sent_set = set(bot_state["sent_deals"])
    candidates = []

    origin_items = list(ORIGINS.items())
    random.shuffle(origin_items)

    for orig_code, orig_meta in origin_items:
        flights_rt = fetch_flights(orig_code, one_way="false")
        flights_ow = fetch_flights(orig_code, one_way="true")
        all_flights = flights_rt + flights_ow

        if not all_flights:
            continue

        dest_prices = {}
        for f in all_flights:
            d_code = f.get("destination")
            p = f.get("price") or f.get("value")
            if d_code and p:
                key = f"{d_code}_{'RT' if f.get('return_at') else 'OW'}"
                dest_prices.setdefault(key, []).append(p)

        dest_avg = {k: sum(v) / len(v) for k, v in dest_prices.items()}

        for f in all_flights:
            dest_code = f.get("destination")
            flight_price_1 = f.get("price") or f.get("value")
            dep_at = f.get("departure_at", "")[:10]
            ret_at = f.get("return_at", "")[:10]

            if not flight_price_1 or not dep_at or dest_code not in CITY_DATA:
                continue

            try:
                dep_date = datetime.strptime(dep_at, "%Y-%m-%d").date()
                days_left = (dep_date - today).days
                if not (0 <= days_left <= MAX_DAYS_AHEAD):
                    continue
            except ValueError:
                continue

            deal_id = f"{orig_code}_{dest_code}_{dep_at}_{ret_at}_{flight_price_1}"
            if deal_id in sent_set:
                continue

            is_rt = bool(ret_at)
            avg_flight_1 = dest_avg.get(f"{dest_code}_{'RT' if is_rt else 'OW'}", flight_price_1)
            if flight_price_1 >= avg_flight_1:
                continue

            dest_info = CITY_DATA[dest_code]
            ddmm_dep = dep_at[8:10] + dep_at[5:7]
            airline_code = f.get("airline", "")
            airline_name = AIRLINES.get(airline_code, f"Рейс {airline_code}" if airline_code else "Регулярный рейс")

            if is_rt:
                try:
                    ret_date = datetime.strptime(ret_at, "%Y-%m-%d").date()
                    nights = (ret_date - dep_date).days
                    if not (5 <= nights <= 15):
                        continue
                except ValueError:
                    continue

                hotel_stay_2 = fetch_hotel_stay_price(
                    dest_info["en"], dep_at, ret_at, dest_info["hotel_base_2p"], nights
                )
                avg_hotel_stay_2 = int(dest_info["hotel_base_2p"] * nights * 1.18)

                flight_price_2 = flight_price_1 * 2
                flight_avg_2 = int(avg_flight_1 * 2)

                tour_price_2 = flight_price_2 + hotel_stay_2
                tour_avg_2 = flight_avg_2 + avg_hotel_stay_2
                tour_price_1 = tour_price_2 // 2

                discount = int((1 - (tour_price_2 / tour_avg_2)) * 100)
                if discount < MIN_TOUR_DISCOUNT:
                    continue

                ddmm_ret = ret_at[8:10] + ret_at[5:7]
                search_route = f"{orig_code}{ddmm_dep}{dest_code}{ddmm_ret}"
                hotel_link = (
                    f"https://search.hotellook.com/?destination={dest_info['en']}"
                    f"&checkIn={dep_at}&checkOut={ret_at}&adults=2&marker={MARKER}&language=ru"
                )

                candidates.append({
                    "deal_id": deal_id,
                    "is_package_tour": True,
                    "priority_score": discount + 20,
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
                    "tour_price_1": tour_price_1,
                    "tour_price_2": tour_price_2,
                    "tour_avg_2": tour_avg_2,
                    "hotel_stay_2": hotel_stay_2,
                    "flight_price_2": flight_price_2,
                    "saved_2": tour_avg_2 - tour_price_2,
                    "hotel_link": hotel_link,
                    "flight_link_2": f"https://www.aviasales.ru/search/{search_route}2?marker={MARKER}",
                    "hashtags": f"{orig_meta['tag']} {dest_info['tag']} #пакетныйтур #отпускподключ"
                })
            else:
                discount = int((1 - (flight_price_1 / avg_flight_1)) * 100)
                if discount < MIN_FLIGHT_DISCOUNT:
                    continue

                flight_avg_1 = int(avg_flight_1)
                flight_price_2 = flight_price_1 * 2
                saved_2 = (flight_avg_1 * 2) - flight_price_2
                search_route = f"{orig_code}{ddmm_dep}{dest_code}"

                candidates.append({
                    "deal_id": deal_id,
                    "is_package_tour": False,
                    "priority_score": discount,
                    "orig_name": orig_meta["name"],
                    "dest_name": dest_info["name"],
                    "photo": dest_info["photo"],
                    "dates_human": f"{format_human_date(dep_date)} (через {days_left} дн.)",
                    "days_left": days_left,
                    "airline": airline_name,
                    "transfer_str": format_transfers(f.get("transfers", 0)),
                    "discount": discount,
                    "flight_price_1": flight_price_1,
                    "flight_avg_1": flight_avg_1,
                    "flight_price_2": flight_price_2,
                    "saved_2": saved_2,
                    "flight_link_1": f"https://www.aviasales.ru/search/{search_route}1?marker={MARKER}",
                    "flight_link_2": f"https://www.aviasales.ru/search/{search_route}2?marker={MARKER}",
                    "hashtags": f"{orig_meta['tag']} {dest_info['tag']} #эксклюзивныйперелет"
                })

        time.sleep(0.5)

    candidates.sort(key=lambda x: x["priority_score"], reverse=True)
    sent_count = 0
    used_routes = set()

    for deal in candidates:
        route_key = f"{deal['orig_name']}_{deal['dest_name']}"
        if route_key in used_routes:
            continue

        html_text, buttons = build_tour_card(deal)
        if send_to_max_channel(deal["photo"], html_text, buttons):
            bot_state["sent_deals"].append(deal["deal_id"])
            used_routes.add(route_key)
            sent_count += 1
            save_state(bot_state)
            time.sleep(4)

        if sent_count >= MAX_DEALS_PER_CYCLE:
            break

# --- ВЕБ-ПУЛЬТ УПРАВЛЕНИЯ И ДИАГНОСТИКИ ---
@app.route("/")
def dashboard():
    discover_target_chat(force_refresh=True)
    chats_html = "".join(
        f"<li><b>{c['title']}</b> — ID: <code>{c['chat_id']}</code> (тип: {c['type']}, статус: {c['status']})</li>"
        for c in diag_info["found_chats"]
    ) or "<li>Каналы пока не обнаружены. Проверьте, тот ли токен бота указан в коде.</li>"

    return f"""
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Пульт Радара Путешествий MAX</title></head>
    <body style="font-family: sans-serif; padding: 20px; background: #121212; color: #f0f0f0;">
        <h2>📡 Пульт управления: Радар Путешествий (MAX)</h2>
        <p><b>Выбранный канал:</b> {diag_info['selected_chat_title'] or 'Не выбран'} (ID: <code>{diag_info['selected_chat_id']}</code>)</p>
        <p><b>Опубликовано постов с момента запуска:</b> {diag_info['posts_sent_count']}</p>
        <p><b>Последний статус отправки:</b> <code>{diag_info['last_send_status']}</code></p>
        <p><a href="/send_now" style="display:inline-block; padding:12px 20px; background:#2b7de9; color:#fff; text-decoration:none; border-radius:8px; font-weight:bold;">🚀 Опубликовать пост прямо сейчас</a></p>
        <hr style="border-color:#333;">
        <h3>Каналы, которые видит бот:</h3>
        <ul>{chats_html}</ul>
    </body>
    </html>
    """, 200

@app.route("/send_now")
def trigger_send_now():
    Thread(target=lambda: publish_editorial_post("morning", force=True), daemon=True).start()
    return redirect("/")

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
