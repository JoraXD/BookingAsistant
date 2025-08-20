"""Text constants for user messages and LLM prompts."""

from pathlib import Path

# User-facing messages for main bot

DEFAULT_QUESTIONS = {
    "from": "Не подскажете, из какого города выезжаем? 🙂",
    "to": "Отлично, осталось уточнить пункт назначения 😉",
    "date": "Хорошо, а дату поездки помните?",
    "transport": "Какой транспорт предпочтёте: автобус, поезд или самолёт?",
}

EXTRA_QUESTIONS = {
    "time": "Во сколько примерно хотите вылететь?",
    "baggage": "Нужен ли дополнительный багаж?",
    "passengers": "Сколько пассажиров поедет?",
}

DEFAULT_FALLBACK = "Кажется, что-то пропустил… Можете повторить, пожалуйста?"

FIELD_NAMES = {
    "from": "город отправления",
    "to": "город назначения",
    "date": "дату",
    "transport": "транспорт",
}

GREETING_MESSAGE = (
    "Привет! Я помогу забронировать поездку. "
    "Расскажите, куда и когда хотите ехать 😄"
)

HELP_MESSAGE = (
    'Отправьте сообщение, например: "Хочу завтра в Москву на поезде".\n'
    "Доступные команды:\n"
    "/start - начать заново\n"
    "/cancel - сбросить сессию"
)

CANCEL_MESSAGE = "Хорошо, начинаем заново. Расскажите ещё раз о поездке!"
SERVICE_ERROR_MESSAGE = "Сервис временно недоступен, попробуйте позже."
NO_TRIPS_MESSAGE = "У вас нет поездок."
TRIP_NOT_FOUND_MESSAGE = "Поездка не найдена."
TRIP_CANCELLED_TEMPLATE = "Поездка в {destination} отменена."
ASK_SEARCH_MESSAGE = "Хотите, я поищу билеты?"
YESNO_PROMPT_USER = "Напишите, пожалуйста, да или нет."
BOOKING_CANCELLED_MESSAGE = (
    "Бронирование отменено. Если захотите, можем попробовать ещё раз!"
)
ROUTES_NOT_FOUND_MESSAGE = "Рейсы не найдены."
REQUEST_SENT_MESSAGE = "Отправили заявку менеджеру"
TRANSPORT_QUESTION_FALLBACK = "Какой транспорт предпочтёте: автобус, поезд или самолёт?"

# Manager bot messages
MANAGER_START_MESSAGE = "Здесь будут появляться новые заявки на бронирование."
MANAGER_BAD_ID_MESSAGE = "Некорректный ID заявки"
MANAGER_TRIP_NOT_FOUND_MESSAGE = "Заявка не найдена"
MANAGER_ACCEPTED_TEMPLATE = "Заявка {trip_id} принята"
MANAGER_ACCEPTED_USER_TEMPLATE = "Вашу заявку №{trip_id} приняли в работу"
MANAGER_BAD_PARAMS_MESSAGE = "Некорректные параметры команды"
MANAGER_AWAITING_PAYMENT_TEMPLATE = "Заявка {trip_id} ожидает оплаты"
MANAGER_PRICE_USER_TEMPLATE = (
    "Стоимость вашей заявки №{trip_id}: {price}. Оплатите по реквизитам: {details}"
)
MANAGER_CONFIRMED_TEMPLATE = "Заявка {trip_id} подтверждена"
MANAGER_TICKET_CAPTION = "Оплата получена, ваш билет готов"
MANAGER_REJECTED_TEMPLATE = "Заявка {trip_id} отклонена"
MANAGER_REJECTED_USER_TEMPLATE = "Вашу заявку №{trip_id} отклонили"
MANAGER_NO_TRIPS_MESSAGE = "Заявки не найдены"
PDF_TICKET_TITLE = "Ticket"

# LLM prompts and templates
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


BASE_PROMPT = _load_prompt("base_prompt.txt")
SLOTS_PROMPT_TEMPLATE = _load_prompt("slots_prompt_template.txt")
COMPLETE_PROMPT_TEMPLATE = _load_prompt("complete_prompt_template.txt")
QUESTION_PROMPT = _load_prompt("question_prompt.txt")
CONFIRM_PROMPT = _load_prompt("confirm_prompt.txt")
FALLBACK_PROMPT = _load_prompt("fallback_prompt.txt")
YESNO_PROMPT = _load_prompt("yesno_prompt.txt")
HISTORY_PROMPT = _load_prompt("history_prompt.txt")
TIME_PROMPT = _load_prompt("time_prompt.txt")
