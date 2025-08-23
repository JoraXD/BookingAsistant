"""Text constants for user messages and LLM prompts."""

# User-facing messages for main bot

DEFAULT_QUESTIONS = {
    "origin": "Не подскажете, из какого города выезжаем? 🙂",
    "destination": "Отлично, осталось уточнить пункт назначения 😉",
    "date": "Хорошо, а дату поездки помните?",
    "transport": "Какой транспорт предпочтёте: автобус, поезд или самолёт?",
}

EXTRA_QUESTIONS = {
    "time": "Во сколько примерно хотите отправиться?",
    "baggage": "Нужен ли дополнительный багаж?",
    "passengers": "На сколько пассажиров нужна бронь?",
}

DEFAULT_FALLBACK = "Кажется, что-то пропустил… Можете повторить, пожалуйста?"

FIELD_NAMES = {
    "origin": "город отправления",
    "destination": "город назначения",
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

# LLM prompts are stored as text files in bookingassistant/prompts
