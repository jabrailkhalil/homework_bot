# handlers/student_handlers.py
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    SessionPersistence, # Для работы с БД напрямую
)

# Импортируем функции CRUD
from database.crud import get_user, create_user
# Импортируем SessionLocal для работы с БД
from database.models import SessionLocal
from sqlalchemy.orm import Session # Для type hint

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определяем состояния для диалога регистрации
GET_CONTACT = range(1) # Теперь только одно состояние

def start(update: Update, context: CallbackContext) -> int:
    """Начинает диалог регистрации при команде /start, если пользователь не найден."""
    user = update.message.from_user
    user_id = user.id
    username = user.username # Получаем username сразу
    logger.info(f"User {user_id} ({username}) started the conversation.")

    # Сохраняем username в context для передачи в следующее состояние
    context.user_data['username'] = username

    db: Session = SessionLocal()
    try:
        db_user = get_user(db, user_id=user_id)
    finally:
        db.close()

    if db_user:
        update.message.reply_text(f"С возвращением, {db_user.full_name}! Вы уже зарегистрированы.")
        return ConversationHandler.END
    else:
        # Создаем кнопку запроса контакта
        contact_keyboard = KeyboardButton(text="Поделиться контактом", request_contact=True)
        custom_keyboard = [[contact_keyboard]]
        reply_markup = ReplyKeyboardMarkup(custom_keyboard, one_time_keyboard=True, resize_keyboard=True)

        update.message.reply_text(
            "Добро пожаловать! Это бот для сдачи домашних заданий.\n"
            "Для начала давайте зарегистрируемся. Пожалуйста, нажмите кнопку ниже, чтобы поделиться вашим контактом.",
            reply_markup=reply_markup
        )
        return GET_CONTACT

def get_contact(update: Update, context: CallbackContext) -> int:
    """Получает контакт пользователя, сохраняет его в БД и завершает диалог."""
    contact = update.message.contact
    user_id = contact.user_id
    first_name = contact.first_name
    last_name = contact.last_name or "" # last_name может отсутствовать
    full_name = f"{first_name} {last_name}".strip()

    # Получаем username из context.user_data, сохраненный в start
    username = context.user_data.get('username')

    logger.info(f"Received contact from user {user_id}: Name={full_name}, Username={username}")

    db: Session = SessionLocal()
    try:
        create_user(db=db, user_id=user_id, full_name=full_name, username=username)
        logger.info(f"User {user_id} ({username}, {full_name}) successfully registered.")
        update.message.reply_text(
            f"Спасибо, {full_name}! Вы успешно зарегистрированы.\n"
            "Теперь вы можете сдавать работы командой /submit.",
            reply_markup=ReplyKeyboardRemove(), # Убираем кастомную клавиатуру
        )
    except Exception as e:
        logger.error(f"Failed to register user {user_id}: {e}")
        update.message.reply_text("Произошла ошибка при регистрации. Попробуйте позже.", reply_markup=ReplyKeyboardRemove())
    finally:
        db.close()

    # Очищаем user_data
    context.user_data.clear()
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Отменяет текущий диалог регистрации."""
    user = update.message.from_user
    logger.info(f"User {user.id} canceled the conversation.")
    update.message.reply_text(
        'Регистрация отменена.', reply_markup=ReplyKeyboardRemove()
    )
    # Очищаем user_data
    context.user_data.clear()
    return ConversationHandler.END

# Создаем ConversationHandler для регистрации
registration_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        GET_CONTACT: [MessageHandler(Filters.contact & ~Filters.command, get_contact)],
        # Состояние GET_GROUP удалено
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    # persistent=True, name="registration_conversation" # Можно добавить персистентность при необходимости
) 