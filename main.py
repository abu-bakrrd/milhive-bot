import telebot
from telebot import types
from rembg import remove
from PIL import Image
from io import BytesIO
import sys
import os
from instagrapi import Client
import time
from dotenv import load_dotenv
import re

# ⬇️ Помощники
def log(msg):
    print(f"[LOG] {msg}")

log('Я запущен!!!')

# Загружаем .env
load_dotenv()

log('Переменные окружения загружены из .env')

# обязательные переменные окружения
required_env = [
    "PASSWORD",
    "LOGIN",
    "CHANNEL",
    "TOKEN",
    "GROUP",
    "CATEGORIES",
    "DELIVERY",
    "ALLOWED_USERS",
    "CYN"
]

# проверка наличия
missing = [var for var in required_env if not os.getenv(var)]
if missing:
    print("❌ Не найдены обязательные переменные окружения:")
    for var in missing:
        print(f" - {var}")
    print("Программа завершится через 10 секунд...")
    time.sleep(10)
    sys.exit(1)
log('Все обязательные переменные окружения найдены')
# инициализация обязательных
PASSWORD = os.getenv("PASSWORD")
LOGIN = os.getenv("LOGIN")
CHANNEL = os.getenv("CHANNEL")
TOKEN = os.getenv("TOKEN")
GROUP = os.getenv("GROUP")
CYN = int(os.getenv("CYN"))  

# CATEGORIES — список; фильтруем пустые элементы
CATEGORIES = [s for s in os.getenv("CATEGORIES", "").split(";") if s]
DELIVERY = os.getenv("DELIVERY", "7–11 дней")

# проверяем ALLOWED_USERS (если некорректно — закрываем через 10 сек)
try:
    ALLOWED_USERS = list(map(int, filter(None, os.getenv("ALLOWED_USERS", "").split(","))))
except Exception:
    print("❌ Ошибка: ALLOWED_USERS содержит некорректные значения.")
    print("Программа завершится через 10 секунд...")
    time.sleep(10)
    sys.exit(1)

# необязательные переменные: списки, безопасная фильтрация
FIRST_STROKES = os.getenv("FIRST_STROKES", "").replace("\\n", "\n").split(";")
FIRST_STROKES = [s for s in FIRST_STROKES if s]

LAST_STROKES = os.getenv("LAST_STROKES", "").replace("\\n", "\n").split(";")
LAST_STROKES = [s for s in LAST_STROKES if s]
log('Переменные окружения успешно инициализированы')

# На VPS используем абсолютные пути или пути относительно рабочей директории скрипта
base_path = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам
LAST_PHOTO_PATH = os.path.join(base_path, "lastPhoto.jpg")
DEFAULT_BG_PATH = os.path.join(base_path, "background.jpg")
log(f'Пути к файлам установлены (базовый путь: {base_path})')

bot = telebot.TeleBot(TOKEN)
user_images = {}
user_states = {}
user_backgrounds = {}

def login():
    global insta, PASSWORD
    log('Авторизация в Instagram...')
    for i in range(3):  # попытки
        try:
            log(f"Попытка авторизации {i + 1}")
            insta = Client()
            insta.login(LOGIN, PASSWORD)
            log("✅ Авторизация в Instagram прошла успешно")
            return insta
        except Exception as e:
            log(f"❌ Ошибка авторизации: {e}")
            time.sleep(3)
    log("❌ Не удалось авторизоваться. Проверьте логин и пароль.")
    return None

insta = login()

def format_price(value):
    # безопасно форматируем число в "1.234.567"
    try:
        return f"{int(value):,}".replace(",", ".")
    except Exception:
        return "0"

def parse_int_amount(text):
    # Парсим число из строки: удаляем пробелы, запятые, точки, оставляем цифры
    if text is None:
        return 0
    s = str(text).strip()
    s = s.replace(" ", "").replace(",", "").replace(".", "")
    s = "".join(ch for ch in s if ch.isdigit())
    if not s:
        return 0
    return int(s)

@bot.message_handler(commands=['id'])
def get_chat_id(message):
    chat_type = message.chat.type
    chat_id = message.chat.id

    if chat_type == "private":
        text = f"👤 Твой ID: `{chat_id}`"
    elif chat_type in ["group", "supergroup"]:
        text = f"👥 ID группы: `{chat_id}`"
    elif chat_type == "channel":
        text = f"📢 ID канала: `{chat_id}`"
    else:
        text = f"ℹ️ Тип чата: {chat_type}, ID: `{chat_id}`"

    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ У тебя нет доступа.")
    bot.send_message(msg.chat.id,
                     "👋 Добро пожаловать!\n\n"
                     "Отправь фото с объектом (можно несколько подряд), и я наложу их на фон.\n"
                     "Заверши отправку фото командой /done\n"
                     "Фон устанавливается через /setbg\n"
                     "Отмени процесс — /cancel\n")

@bot.message_handler(commands=['setbg'])
def set_background_start(msg):
    if msg.from_user.id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ Нет доступа.")
    bot.send_message(msg.chat.id, "📸 Отправь изображение для фона.")
    user_images[msg.chat.id] = {'awaiting_bg': True}

@bot.message_handler(commands=['done'])
def finish_upload(msg):
    chat_id = msg.chat.id
    if chat_id not in user_images or not user_images[chat_id].get('photos'):
        return bot.send_message(chat_id, "❌ Сначала отправьте хотя бы одно фото.")
    bot.send_message(chat_id, "💰 Введите себестомость в юанях:")
    user_states[chat_id] = {
        'step': 'cprice',
        'images': user_images[chat_id]['photos']
    }
    user_images.pop(chat_id)
    log(f"{chat_id}: Завершена загрузка фото. Переход к этапу ввода цены.")

@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    if user_id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ У тебя нет доступа.")
    file_info = bot.get_file(msg.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file)).convert("RGBA")

    if chat_id in user_images and user_images[chat_id].get('awaiting_bg'):
        user_backgrounds[chat_id] = image
        user_images.pop(chat_id)
        return bot.send_message(chat_id, "✅ Фон успешно установлен.")

    if chat_id not in user_backgrounds:
        try:
            default_bg = Image.open(DEFAULT_BG_PATH).convert("RGBA")
            user_backgrounds[chat_id] = default_bg
            log("🖼 Использован фон по умолчанию.")
        except Exception as e:
            return bot.send_message(chat_id, f"❌ Не удалось загрузить фон по умолчанию: {e}")
    if chat_id not in user_images:
        user_images[chat_id] = {'photos': []}
    user_images[chat_id]['photos'].append(image)
    bot.send_message(chat_id, "📥 Фото добавлено. Отправь следующее или напиши /done")

@bot.message_handler(commands=['cancel'])
def cancel_process(msg):
    chat_id = msg.chat.id
    user_images.pop(chat_id, None)
    user_states.pop(chat_id, None)
    bot.send_message(chat_id, "🔄 Процесс отменён.")

@bot.message_handler(content_types=['text'])
def handle_text(msg):
    chat_id = msg.chat.id
    if chat_id not in user_states:
        return
    state = user_states[chat_id]
    text = msg.text.strip()

    match state['step']:
        case 'cprice':
            try:
                cny = float(text.replace(",", "."))
            except Exception:
                bot.send_message(chat_id, "❌ Некорректная себестоимость. Введите число, например: 12.5")
                return
            price_in_uzs = cny * CYN
            suggested_price = round((price_in_uzs * 1.5) + 50000, -3)
            bot.send_message(chat_id, f"💰 Себестоимость в юанях: ~{text} CNY\n"
                                      f"💰 Себестоимость в суммах: {format_price(price_in_uzs)} UZS\n"
                                      f"💡 Рекомендуемая цена: {format_price(suggested_price)} UZS")
            log(f"{chat_id}: Введена себестоимость: {text} CNY, {format_price(price_in_uzs)} UZS")
            state['cprice'] = price_in_uzs
            state['step'] = 'category'
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            for cat in CATEGORIES:
                markup.add(types.KeyboardButton(cat))
            bot.send_message(chat_id, "🏷 Категория:", reply_markup=markup)
        case 'category':
            state['category'] = '#' + '_'.join(text.split(' '))
            state['step'] = 'brand'
            bot.send_message(chat_id, "🧵 Бренд:", reply_markup=types.ReplyKeyboardRemove())
            log(f"{chat_id}: Введена категория: {text}")
        case 'brand':
            state['brand'] = text
            state['step'] = 'size'
            bot.send_message(chat_id, "📏 Размеры:")
            log(f"{chat_id}: Введён бренд: {text}")
        case 'size':
            state['size'] = text
            state['step'] = 'color'
            bot.send_message(chat_id, "🎨 Цвета:")
            log(f"{chat_id}: Введены размеры: {text}")
        case 'color':
            state['color'] = text
            state['step'] = 'plink'
            bot.send_message(chat_id, "🔗 Ссылка на товар:")
            log(f"{chat_id}: Введён цвет: {text}")
        case 'plink':
            state['plink'] = text
            state['step'] = 'price'
            bot.send_message(chat_id, "💰 Цена в суммах:")
            log(f"{chat_id}: Введена ссылка на товар: {text}")
        case 'price':
            amount = parse_int_amount(text)
            if amount == 0:
                bot.send_message(chat_id, "❌ Некорректная цена. Введите число, например: 120000")
                return
            state['price'] = amount
            state['step'] = 'withcargo'
            log(f"{chat_id}: Введена цена: {amount}")
            bot.send_message(chat_id, "🚚 Цена карго включена в цену?", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет"))
        case 'withcargo':
            if text not in ["✅ Да", "❌ Нет"]:
                return bot.send_message(chat_id, "❌ Пожалуйста, выберите '✅ Да' или '❌ Нет'.")
            state['withcargo'] = (text == "✅ Да")
            log(f"{chat_id}: Введён статус с доставкой: {text}")
            state['step'] = 'name'
            bot.send_message(chat_id, "📝 Название:")
        case 'name':
            state['name'] = text
            state['step'] = 'availability'
            bot.send_message(chat_id, "Товар в наличии?", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет"))
            log(f"{chat_id}: Введено название: {text}")
        case 'availability':
            if text not in ["✅ Да", "❌ Нет"]:
                return bot.send_message(chat_id, "❌ Пожалуйста, выберите '✅ Да' или '❌ Нет'.")
            state['availability'] = (text == "✅ Да")
            bot.send_message(chat_id, "Удалить фон с фотографий?", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет"))
            state['step'] = 'bg'
            log(f"{chat_id}: Введён статус наличия: {text}. Переход к этапу обработки фона.")
        case 'bg':
            if text == "❌ Нет":
                processed_images = []
                for image in state['images']:
                    output = BytesIO()
                    image.save(output, format="PNG")
                    output.seek(0)
                    processed_images.append(output)
                state['images'] = processed_images
            elif text == "✅ Да":
                process_message = bot.send_message(chat_id, "🛠 Обрабатываю фотографии... 0%")
                processed_images = []
                for image in state['images']:
                    buffered = BytesIO()
                    image.save(buffered, format="PNG")
                    try:
                        no_bg = remove(buffered.getvalue())
                    except Exception as e:
                        return bot.send_message(chat_id, f"❌ Ошибка при удалении фона: {e}")

                    object_no_bg = Image.open(BytesIO(no_bg)).convert("RGBA")
                    bg = user_backgrounds[chat_id].copy()
                    bg_w, bg_h = bg.size
                    obj_w, obj_h = object_no_bg.size
                    scale = min((bg_w * 0.7) / obj_w, (bg_h * 0.7) / obj_h)
                    new_size = (int(obj_w * scale), int(obj_h * scale))
                    object_resized = object_no_bg.resize(new_size, Image.LANCZOS)
                    pos = ((bg_w - new_size[0]) // 2, (bg_h - new_size[1]) // 2)
                    bg.paste(object_resized, pos, object_resized)
                    output = BytesIO()
                    bg.save(output, format="PNG")
                    output.seek(0)
                    processed_images.append(output)
                    procent = int((len(processed_images) / len(state['images'])) * 100)
                    try:
                        bot.edit_message_text(chat_id=chat_id, message_id=process_message.message_id, text=f"🛠 Обрабатываю фотографии... {procent}%")
                    except Exception:
                        pass

                state['images'] = processed_images

            caption_parts = []
            if FIRST_STROKES:
                caption_parts.append("\n".join(FIRST_STROKES))

            caption_parts.append(f"<b>📌 {state['name'].strip()}</b>")

            if state.get("availability"):
                caption_parts.append(f"📦 <i><b>Товар в наличии!</b></i>")

            if state.get('price', '-') != '-':
                if state['availability']:
                    caption_parts.append(f"💸 <b>Цена:</b> <code>{format_price(state['price'])}</code>")
                else:
                    caption_parts.append(f"💸 <b>Цена:</b> <code>{format_price(state['price'])} + Карго</code>")
            if state.get('category', '-') != '-':
                caption_parts.append(f"🏷 <b>Категория:</b> {state.get('category', '—')}")

            if state.get('brand', '-') != '-':
                caption_parts.append(f"👔 <b>Бренд:</b> {state.get('brand', '—')}")

            if state.get('size', '-') != '-':
                caption_parts.append(f"📏 <b>Размеры:</b> {state.get('size', '—')}")
            if state.get('color', '-') != '-':
                caption_parts.append(f"🎨 <b>Цвет:</b> {state.get('color', '—')}")

            caption_parts.append("")

            if not state.get('availability'):
                caption_parts.append(f"🚚 <b>Доставка:</b> <i>{DELIVERY}</i>")

            if LAST_STROKES:
                caption_parts.append("\n".join(LAST_STROKES))

            caption = "\n".join([p for p in caption_parts if p])
            state['caption'] = caption

            media_group = []
            for i, img in enumerate(state['images']):
                img.seek(0)
                media = types.InputMediaPhoto(img, caption=caption if i == 0 else None, parse_mode="HTML")
                media_group.append(media)
            bot.send_media_group(chat_id, media_group)
            bot.send_message(chat_id, "Опубликовать в канал?", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Да", "❌ Нет"))
            state['step'] = 'posting'
            log(f"{chat_id}: Фон обработан. Переход к этапу публикации.")
        case 'posting':
            if text == "✅ Да":
                media_group = []
                for i, img in enumerate(state['images']):
                    img.seek(0)
                    media = types.InputMediaPhoto(img, caption=state['caption'] if i == 0 else None, parse_mode="HTML")
                    media_group.append(media)

                message = bot.send_media_group(CHANNEL, media_group)
                post_link = f"https://t.me/{CHANNEL[1:]}/{message[0].message_id}"
                state['tlink'] = post_link

                log("🟣 Публикация в Instagram...")
                if insta:
                    try:
                        photo_paths = []
                        for i, img in enumerate(state['images']):
                            img.seek(0)
                            path = os.path.join(base_path, f"temp{i}.jpg")
                            with open(path, "wb") as f:
                                f.write(img.read())
                            photo_paths.append(path)

                        if os.path.exists(LAST_PHOTO_PATH):
                            photo_paths.append(LAST_PHOTO_PATH)
                            log("✅ Бренд-фото добавлено")
                        else:
                            log("⚠️ Бренд-фото не найден")

                        caption_for_insta = state['caption']
                        for tag in ["b", "i", "code", "u", "s", "strong", "em"]:
                            caption_for_insta = caption_for_insta.replace(f"<{tag}>", "").replace(f"</{tag}>", "")

                        caption_for_insta = re.sub(r"<a [^>]*>(.*?)</a>", r"\1", caption_for_insta)
                        caption_for_insta = re.sub(r"<(br|hr|img|video|source)[^>]*>", "", caption_for_insta)
                        caption_for_insta = re.sub(r"<[^>]+>", "", caption_for_insta)

                        if not photo_paths:
                            raise RuntimeError("Нет изображений для отправки в Instagram")

                        if len(photo_paths) == 1:
                            insta.photo_upload(photo_paths[0], caption_for_insta)
                            log("✅ Фото опубликовано как пост в Instagram")
                        else:
                            insta.album_upload(photo_paths, caption_for_insta)
                            log("✅ Фото опубликованы как альбом в Instagram")

                    except Exception as e:
                        log(f"❌ Ошибка Instagram: {e}")
                    finally:
                        for path in photo_paths:
                            if "temp" in os.path.basename(path) and os.path.exists(path):
                                try:
                                    os.remove(path)
                                    log(f"🗑 Удалён временный файл: {path}")
                                except Exception as ex:
                                    log(f"⚠️ Не удалось удалить {path}: {ex}")

                report_caption = [
                    f"🟢 Новая публикация! ID: {state['tlink'].split('/')[-1]}",
                    f"🔗 Ссылка на пост: {state.get('tlink', '—')}",
                    f"📝 Название: {state.get('name', '—')}",
                    f"💸 Цена: {format_price(state.get('price', 0))} UZS",
                    f"Себестоимость: {format_price(state.get('cprice', 0)/CYN) if state.get('cprice') else '—'} CNY (~{format_price(state.get('cprice', 0))} UZS)",
                    f"🏷 Категория: {state.get('category', '—')}",
                    f"👔 Бренл: {state.get('brand', '—')}",
                    f"📏 Размеры: {state.get('size', '—')}",
                    f"🎨 Цвет: {state.get('color', '—')}",
                    f"🔗 Ссылка на товар: {state.get('plink', '—')}",
                ]
                report_text = "\n".join(report_caption)
                report = []
                for i, img in enumerate(state['images']):
                    img.seek(0)
                    media = types.InputMediaPhoto(img, caption=report_text if i == 0 else None, parse_mode="HTML")
                    report.append(media)
                bot.send_media_group(GROUP, report)

            user_states.pop(chat_id, None)
            bot.send_message(chat_id, "✅ Готово!")
            log(f"{chat_id}: Публикация завершена. Данные сохранены в группе.")

bot.infinity_polling()
