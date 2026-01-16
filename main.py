import telebot
import requests
import re
from telebot import types

# Замените на ваш токен от @BotFather
BOT_TOKEN = 'тут токен'

bot = telebot.TeleBot(BOT_TOKEN)

# User-Agent для запросов к HH.ru
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Хранилище состояний пользователей
user_states = {}

# Список доступных уровней опыта
EXPERIENCE_LEVELS = {
    'noExperience': 'Нет опыта',
    'between1And3': '1-3 года',
    'between3And6': '3-6 лет',
    'moreThan6': 'Более 6 лет'
}

# Популярные города (ID из API HH.ru)
POPULAR_CITIES = {
    '1': 'Москва',
    '2': 'Санкт-Петербург',
    '3': 'Екатеринбург',
    '4': 'Новосибирск',
    '88': 'Казань',
    '66': 'Нижний Новгород',
    '1438': 'Минск',
    '160': 'Алматы',
    '2019': 'Ташкент'
}


def escape_markdown_v2(text):
    """
    Надежное экранирование всех специальных символов для MarkdownV2
    """
    if not text:
        return ""
    # Все специальные символы для MarkdownV2
    special_chars = r'_*[]()~`>#+-=|{}.!'
    result = str(text)
    for char in special_chars:
        result = result.replace(char, '\\' + char)
    return result


def fetch_vacancies(profession, filters):
    """
    Выполняет запрос к API HH.ru с указанными параметрами
    """
    base_url = 'https://api.hh.ru/vacancies'
    params = {
        'text': profession,
        'per_page': 10,
        'page': 0
    }

    # Применение фильтров
    if filters.get('with_salary') or filters.get('min_salary'):
        params['only_with_salary'] = 'true'

    if filters.get('min_salary'):
        params['salary'] = str(filters['min_salary'])

    if filters.get('remote'):
        params['schedule'] = 'remote'

    if filters.get('experience'):
        params['experience'] = filters['experience']

    if filters.get('city'):
        params['area'] = filters['city']
    elif filters.get('city_name'):
        # Если указано название города (custom), ищем по названию через text
        params['text'] = f"{profession} {filters['city_name']}"

    try:
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get('items'):
            return None, "Вакансий не найдено"

        return data['items'], None

    except requests.exceptions.RequestException as e:
        return None, f"Ошибка запроса к HH.ru: {str(e)}"
    except ValueError as e:
        return None, f"Ошибка обработки ответа: {str(e)}"
    except Exception as e:
        return None, f"Неизвестная ошибка: {str(e)}"


def search_city_by_name(city_name):
    """
    Ищет ID города по его названию через API HH.ru
    """
    try:
        response = requests.get(
            'https://api.hh.ru/areas',
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        areas = response.json()

        # Рекурсивный поиск города
        def find_city(areas_list, name):
            name_lower = name.lower()
            for area in areas_list:
                if area['name'].lower() == name_lower:
                    return area['id']
                if 'areas' in area and area['areas']:
                    result = find_city(area['areas'], name)
                    if result:
                        return result
            return None

        city_id = find_city(areas, city_name)
        return city_id
    except Exception as e:
        print(f"Ошибка поиска города: {e}")
        return None


def format_salary(salary_data):
    """Форматирует информацию о зарплате для отображения"""
    if not salary_data:
        return "не указана"

    currency = salary_data.get('currency', 'RUR')
    # Конвертируем код валюты в символ
    currency_map = {
        'RUR': '₽',
        'USD': '$',
        'EUR': '€',
        'KZT': '₸',
        'BYR': 'Br'
    }
    currency_symbol = currency_map.get(currency, currency)

    salary_from = salary_data.get('from')
    salary_to = salary_data.get('to')

    parts = []
    if salary_from:
        parts.append(f"от {salary_from}")
    if salary_to:
        parts.append(f"до {salary_to}")

    if not parts:
        return "не указана"

    return f"{' '.join(parts)} {currency_symbol}"


def format_vacancy(vacancy):
    """Форматирует одну вакансию в markdown"""
    # Безопасное получение данных с экранированием
    name = escape_markdown_v2(vacancy.get('name', ''))
    company = escape_markdown_v2(vacancy.get('employer', {}).get('name', 'Не указана'))
    city = escape_markdown_v2(vacancy.get('area', {}).get('name', 'Не указан'))
    url = vacancy.get('alternate_url', '')

    # Форматируем зарплату отдельно и экранируем
    salary_str = escape_markdown_v2(format_salary(vacancy.get('salary')))

    return (
        f"💼 *{name}*\n"
        f"🏢 {company}\n"
        f"💰 {salary_str}\n"
        f"📍 {city}\n"
        f"[Ссылка на вакансию ➡️]({url})"
    )


def create_main_menu():
    """Создает главное меню с кнопками"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🔍 Найти вакансии")
    btn2 = types.KeyboardButton("ℹ️ Помощь")
    markup.add(btn1, btn2)
    return markup


def create_filters_keyboard(filters):
    """Создает клавиатуру для настройки фильтров"""
    markup = types.InlineKeyboardMarkup(row_width=1)

    # Кнопка "С зарплатой"
    salary_text = "✅ Только с зарплатой" if filters.get('with_salary') else "С зарплатой"
    markup.add(types.InlineKeyboardButton(salary_text, callback_data="toggle_salary"))

    # Кнопка минимальной зарплаты
    min_salary = filters.get('min_salary', 'не указана')
    min_salary_text = f"💰 Мин. зарплата: {min_salary}"
    markup.add(types.InlineKeyboardButton(min_salary_text, callback_data="set_min_salary"))

    # Кнопка удаленной работы
    remote_text = "✅ Только удалёнка" if filters.get('remote') else "Удалённая работа"
    markup.add(types.InlineKeyboardButton(remote_text, callback_data="toggle_remote"))

    # Кнопка города
    city_id = filters.get('city', '')
    city_name = filters.get('city_name', '')
    if city_name:
        display_city = city_name
    elif city_id:
        display_city = POPULAR_CITIES.get(city_id, 'установлен')
    else:
        display_city = 'любой'
    city_text = f"🏙 Город: {display_city}"
    markup.add(types.InlineKeyboardButton(city_text, callback_data="set_city"))

    # Кнопка опыта
    exp_level = filters.get('experience', '')
    exp_text = f"💼 Опыт: {EXPERIENCE_LEVELS.get(exp_level, 'любой')}"
    markup.add(types.InlineKeyboardButton(exp_text, callback_data="set_experience"))

    # Кнопка поиска
    markup.add(types.InlineKeyboardButton("🚀 Начать поиск", callback_data="search_jobs"))

    # Кнопка отмены
    markup.add(types.InlineKeyboardButton("❌ Отменить поиск", callback_data="cancel_search"))

    return markup


def create_experience_keyboard():
    """Создает клавиатуру для выбора опыта"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for exp_id, exp_name in EXPERIENCE_LEVELS.items():
        markup.add(types.InlineKeyboardButton(exp_name, callback_data=f"exp_{exp_id}"))
    markup.add(types.InlineKeyboardButton("Любой опыт", callback_data="exp_any"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_filters"))
    return markup


def create_city_keyboard():
    """Создает клавиатуру для выбора города"""
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Создаем кнопки для популярных городов
    buttons = []
    for city_id, city_name in POPULAR_CITIES.items():
        buttons.append(types.InlineKeyboardButton(city_name, callback_data=f"city_{city_id}"))

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])

    # Кнопка для ввода своего города
    markup.add(types.InlineKeyboardButton("✍️ Ввести свой город", callback_data="city_custom"))

    # Кнопки "Любой город" и "Назад"
    markup.add(types.InlineKeyboardButton("🌍 Любой город", callback_data="city_any"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_filters"))
    return markup


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    # Очищаем состояние пользователя
    if chat_id in user_states:
        del user_states[chat_id]

    welcome_text = (
        "👋 Добро пожаловать в JobFinder Bot!\n\n"
        "Я помогу вам найти лучшие вакансии на HH.ru\n"
        "Используйте кнопки ниже для начала поиска"
    )

    bot.send_message(
        chat_id,
        welcome_text,
        reply_markup=create_main_menu()
    )


@bot.message_handler(func=lambda message: message.text == "ℹ️ Помощь")
def send_help(message):
    help_text = (
        "<b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажмите <b>'🔍 Найти вакансии'</b>\n"
        "2️⃣ Введите название профессии\n"
        "3️⃣ Настройте фильтры с помощью кнопок:\n"
        "   • <b>С зарплатой</b> - только вакансии с указанной ЗП\n"
        "   • <b>Мин. зарплата</b> - установите минимальный порог\n"
        "   • <b>Удалённая работа</b> - только remote-вакансии\n"
        "   • <b>Город</b> - выберите город для поиска\n"
        "   • <b>Опыт</b> - выберите требуемый опыт работы\n"
        "4️⃣ Нажмите <b>'🚀 Начать поиск'</b> для получения результатов\n\n"
        "💡 <i>Совет:</i> Вы можете сбросить фильтры, начав новый поиск"
    )

    bot.send_message(
        message.chat.id,
        help_text,
        reply_markup=create_main_menu(),
        parse_mode='HTML'
    )


@bot.message_handler(func=lambda message: message.text == "🔍 Найти вакансии")
def start_job_search(message):
    chat_id = message.chat.id

    # Инициализируем состояние пользователя
    user_states[chat_id] = {
        'step': 'waiting_profession',
        'profession': '',
        'filters': {}
    }

    bot.send_message(
        chat_id,
        "🔍 <b>Введите название профессии для поиска</b>\n\n"
        "Примеры: <code>Python developer</code>, <code>Data scientist</code>, <code>Product manager</code>",
        parse_mode='HTML',
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'waiting_profession')
def handle_profession(message):
    chat_id = message.chat.id

    if chat_id not in user_states:
        bot.send_message(chat_id, "Сессия устарела. Начните поиск заново.", reply_markup=create_main_menu())
        return

    profession = message.text.strip()

    if len(profession) < 2:
        bot.send_message(chat_id, "Название профессии слишком короткое. Попробуйте еще раз:")
        return

    user_states[chat_id]['profession'] = profession
    user_states[chat_id]['step'] = 'setting_filters'

    filters = user_states[chat_id]['filters']

    bot.send_message(
        chat_id,
        f"✅ Профессия: <b>{profession}</b>\n\n"
        "Теперь настройте фильтры поиска:",
        parse_mode='HTML',
        reply_markup=create_filters_keyboard(filters)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_"))
def handle_toggle_filters(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    filters = user_states[chat_id]['filters']

    if call.data == "toggle_salary":
        filters['with_salary'] = not filters.get('with_salary', False)
    elif call.data == "toggle_remote":
        filters['remote'] = not filters.get('remote', False)

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"✅ Профессия: <b>{user_states[chat_id]['profession']}</b>\n\nНастройте фильтры:",
        parse_mode='HTML',
        reply_markup=create_filters_keyboard(filters)
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "set_min_salary")
def handle_set_min_salary(call):
    chat_id = call.message.chat.id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    user_states[chat_id]['step'] = 'waiting_min_salary'

    bot.send_message(
        chat_id,
        "💰 <b>Введите минимальную зарплату (в рублях):</b>\n\n"
        "Пример: <code>100000</code> или <code>150000</code>",
        parse_mode='HTML'
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'waiting_min_salary')
def handle_min_salary_input(message):
    chat_id = message.chat.id

    if chat_id not in user_states:
        bot.send_message(chat_id, "Сессия устарела. Начните поиск заново.", reply_markup=create_main_menu())
        return

    try:
        # Очищаем ввод от пробелов и разделителей
        clean_text = re.sub(r'[^\d]', '', message.text)
        salary = int(clean_text)

        if salary < 10000:
            raise ValueError

        user_states[chat_id]['filters']['min_salary'] = salary
        user_states[chat_id]['step'] = 'setting_filters'

        filters = user_states[chat_id]['filters']

        bot.send_message(
            chat_id,
            f"✅ Минимальная зарплата установлена: <b>{salary:,} ₽</b>\n\n"
            "Вы можете продолжить настройку фильтров:",
            parse_mode='HTML',
            reply_markup=create_filters_keyboard(filters)
        )
    except ValueError:
        bot.send_message(
            chat_id,
            "❌ Некорректное значение. Введите целое число (в рублях):\n"
            "Пример: <code>100000</code>",
            parse_mode='HTML'
        )


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('step') == 'waiting_city_name')
def handle_city_name_input(message):
    chat_id = message.chat.id

    if chat_id not in user_states:
        bot.send_message(chat_id, "Сессия устарела. Начните поиск заново.", reply_markup=create_main_menu())
        return

    city_name = message.text.strip()

    if len(city_name) < 2:
        bot.send_message(
            chat_id,
            "❌ Название города слишком короткое. Попробуйте еще раз:",
            parse_mode='HTML'
        )
        return

    # Ищем ID города через API
    bot.send_message(chat_id, f"🔍 Ищу город <b>'{city_name}'</b>...", parse_mode='HTML')

    city_id = search_city_by_name(city_name)

    if city_id:
        # Город найден - используем ID
        user_states[chat_id]['filters']['city'] = city_id
        user_states[chat_id]['filters']['city_name'] = city_name
        success_msg = f"✅ Город <b>'{city_name}'</b> найден и установлен!"
    else:
        # Город не найден - сохраняем название для поиска по тексту
        user_states[chat_id]['filters']['city_name'] = city_name
        if 'city' in user_states[chat_id]['filters']:
            del user_states[chat_id]['filters']['city']
        success_msg = f"✅ Установлен поиск по названию: <b>'{city_name}'</b>\n\n" \
                      "⚠️ <i>Точное совпадение не найдено в базе HH.ru, " \
                      "будет выполнен текстовый поиск</i>"

    user_states[chat_id]['step'] = 'setting_filters'
    filters = user_states[chat_id]['filters']

    bot.send_message(
        chat_id,
        success_msg + "\n\nВы можете продолжить настройку фильтров:",
        parse_mode='HTML',
        reply_markup=create_filters_keyboard(filters)
    )


@bot.callback_query_handler(func=lambda call: call.data == "set_experience")
def handle_set_experience(call):
    chat_id = call.message.chat.id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="<b>💼 Выберите требуемый опыт работы:</b>",
        parse_mode='HTML',
        reply_markup=create_experience_keyboard()
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "set_city")
def handle_set_city(call):
    chat_id = call.message.chat.id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="<b>🏙 Выберите город для поиска:</b>",
        parse_mode='HTML',
        reply_markup=create_city_keyboard()
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("exp_"))
def handle_experience_selection(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    exp_data = call.data.split('_')[1]

    if exp_data == "any":
        if 'experience' in user_states[chat_id]['filters']:
            del user_states[chat_id]['filters']['experience']
    else:
        user_states[chat_id]['filters']['experience'] = exp_data

    filters = user_states[chat_id]['filters']

    if exp_data == "any" or exp_data in EXPERIENCE_LEVELS:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ Профессия: <b>{user_states[chat_id]['profession']}</b>\n\nНастройте фильтры:",
            parse_mode='HTML',
            reply_markup=create_filters_keyboard(filters)
        )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("city_"))
def handle_city_selection(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    city_data = call.data.split('_', 1)[1]

    if city_data == "any":
        # Убираем все фильтры по городу
        if 'city' in user_states[chat_id]['filters']:
            del user_states[chat_id]['filters']['city']
        if 'city_name' in user_states[chat_id]['filters']:
            del user_states[chat_id]['filters']['city_name']

        filters = user_states[chat_id]['filters']
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ Профессия: <b>{user_states[chat_id]['profession']}</b>\n\nНастройте фильтры:",
            parse_mode='HTML',
            reply_markup=create_filters_keyboard(filters)
        )
    elif city_data == "custom":
        # Переход к вводу своего города
        user_states[chat_id]['step'] = 'waiting_city_name'
        bot.send_message(
            chat_id,
            "🏙 <b>Введите название города:</b>\n\n"
            "Примеры: <code>Воронеж</code>, <code>Краснодар</code>, <code>Самара</code>",
            parse_mode='HTML'
        )
        bot.delete_message(chat_id, message_id)
    else:
        # Выбран город из списка
        user_states[chat_id]['filters']['city'] = city_data
        # Удаляем custom город если был
        if 'city_name' in user_states[chat_id]['filters']:
            del user_states[chat_id]['filters']['city_name']

        filters = user_states[chat_id]['filters']
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ Профессия: <b>{user_states[chat_id]['profession']}</b>\n\nНастройте фильтры:",
            parse_mode='HTML',
            reply_markup=create_filters_keyboard(filters)
        )

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_filters")
def handle_back_to_filters(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    filters = user_states[chat_id]['filters']

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"✅ Профессия: <b>{user_states[chat_id]['profession']}</b>\n\nНастройте фильтры:",
        parse_mode='HTML',
        reply_markup=create_filters_keyboard(filters)
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "search_jobs")
def handle_search(call):
    chat_id = call.message.chat.id

    if chat_id not in user_states:
        bot.answer_callback_query(call.id, "Сессия устарела. Начните поиск заново.", show_alert=True)
        return

    profession = user_states[chat_id]['profession']
    filters = user_states[chat_id]['filters']

    bot.send_message(chat_id, f"🚀 Ищу вакансии по запросу <b>'{profession}'</b>...", parse_mode='HTML')

    vacancies, error = fetch_vacancies(profession, filters)

    if error:
        bot.send_message(
            chat_id,
            f"❌ {error}",
            reply_markup=create_main_menu()
        )
        if chat_id in user_states:
            del user_states[chat_id]
        bot.answer_callback_query(call.id)
        return

    if not vacancies:
        bot.send_message(
            chat_id,
            "❌ Вакансий по вашему запросу не найдено",
            reply_markup=create_main_menu()
        )
        if chat_id in user_states:
            del user_states[chat_id]
        bot.answer_callback_query(call.id)
        return

    # Формируем результаты
    profession_escaped = escape_markdown_v2(profession)
    result_text = f"✅ Найдено *{len(vacancies)}* вакансий по запросу *{profession_escaped}*:\n\n"

    for i, vac in enumerate(vacancies[:10], 1):
        result_text += f"{i}\\. {format_vacancy(vac)}\n\n"

    # Добавляем кнопку для нового поиска
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Новый поиск"))
    markup.add(types.KeyboardButton("🏠 В главное меню"))

    try:
        bot.send_message(
            chat_id,
            result_text,
            parse_mode='MarkdownV2',
            disable_web_page_preview=True,
            reply_markup=markup
        )
    except Exception as e:
        # Если ошибка форматирования, отправляем простым текстом
        simple_text = f"✅ Найдено {len(vacancies)} вакансий по запросу '{profession}':\n\n"

        for i, vac in enumerate(vacancies[:10], 1):
            name = vac.get('name', '')
            company = vac.get('employer', {}).get('name', 'Не указана')
            city = vac.get('area', {}).get('name', 'Не указан')
            salary_str = format_salary(vac.get('salary'))
            url = vac.get('alternate_url', '')

            simple_text += (
                f"{i}. 💼 {name}\n"
                f"🏢 {company}\n"
                f"💰 {salary_str}\n"
                f"📍 {city}\n"
                f"🔗 {url}\n\n"
            )

        bot.send_message(
            chat_id,
            simple_text,
            disable_web_page_preview=True,
            reply_markup=markup
        )

    # Удаляем состояние после завершения поиска
    if chat_id in user_states:
        del user_states[chat_id]
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_search")
def handle_cancel_search(call):
    chat_id = call.message.chat.id

    if chat_id in user_states:
        del user_states[chat_id]

    bot.send_message(
        chat_id,
        "❌ Поиск отменён",
        reply_markup=create_main_menu()
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: message.text == "🔍 Новый поиск")
def new_search(message):
    start_job_search(message)


@bot.message_handler(func=lambda message: message.text == "🏠 В главное меню")
def back_to_main_menu(message):
    send_welcome(message)


@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(
        message.chat.id,
        "Неизвестная команда. Используйте кнопки для навигации:",
        reply_markup=create_main_menu()
    )


if __name__ == '__main__':
    print("JobFinder Bot запущен...")
    print("Для остановки нажмите Ctrl+C")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\nБот остановлен")