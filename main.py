import os
import logging
from typing import Optional, List
from telegram import Update
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext,
)

# --- «асинхронный» декоратор (доступен в PTB-13) ---------------------------
try:                             # в разных релизах он лежит в разных модулях
    from telegram.ext.dispatcher import run_async
except ImportError:
    from telegram.ext import run_async

# Google Drive
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow    import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload

# проектные модули
from private_config import (
    TELEGRAM_TOKEN, GOOGLE_CLIENT_SECRET_FILE,
    GOOGLE_TOKEN_FILE, GOOGLE_SCOPES,
)
from database import models, crud
from database.models import SessionLocal
from handlers.student_handlers import registration_handler

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  ИНИЦИАЛИЗАЦИЯ БД
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Создаёт таблицы, если их ещё нет."""
    models.Base.metadata.create_all(bind=models.engine)
    logger.info("DB initialised")


# ---------------------------------------------------------------------------
#  Google Drive helpers
# ---------------------------------------------------------------------------
def _get_drive_service():
    creds: Optional[Credentials] = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRET_FILE, GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def upload_file(local_path: str, file_name: str, mime_type: str) -> str:
    """Возвращает Drive-ID загруженного файла."""
    service = _get_drive_service()
    meta   = {"name": file_name}
    media  = MediaFileUpload(local_path, mimetype=mime_type)
    file   = service.files().create(body=meta, media_body=media, fields="id").execute()
    return file["id"]


# ---------------------------------------------------------------------------
#  ХЕНДЛЕРЫ
# ---------------------------------------------------------------------------
def help_cmd(update: Update, _: CallbackContext) -> None:
    update.message.reply_text(
        "/start — регистрация\n"
        "/submit — отправить ДЗ\n"
        "/submitted — мои сдачи\n"
        "/help — помощь"
    )

def submit_cmd(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Пришлите файл-документ с домашней работой.")

@run_async
def handle_document(update: Update, context: CallbackContext) -> None:
    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or "homework"
    mime_type = doc.mime_type or "application/octet-stream"

    # временный файл
    tmp_dir = "temp"
    os.makedirs(tmp_dir, exist_ok=True)
    local   = os.path.join(tmp_dir, file_name)

    try:
        doc.get_file().download(custom_path=local)
        drive_id = upload_file(local, file_name, mime_type)

        # сохраняем запись в БД
        db = SessionLocal()
        try:
            crud.create_submission(db, update.effective_user.id, file_name, drive_id)
        finally:
            db.close()

        update.message.reply_text(f"✅ «{file_name}» загружен. Drive-ID: {drive_id}")
    except Exception as err:
        logger.exception("Upload error: %s", err)
        update.message.reply_text("❌ Не удалось загрузить файл. Попробуйте ещё раз.")
    finally:
        if os.path.exists(local):
            os.remove(local)

def submitted_cmd(update: Update, _: CallbackContext) -> None:
    db = SessionLocal()
    try:
        subs = crud.get_submissions_by_user(db, update.effective_user.id)
    finally:
        db.close()

    if not subs:
        update.message.reply_text("Вы ещё не сдавали домашних работ.")
        return

    def fmt(idx, s) -> str:
        when = s.submitted_at.strftime("%d.%m.%Y %H:%M")
        return f"{idx}. {s.file_name} — {when}"

    text = "Ваши сдачи:\n" + "\n".join(fmt(i, s) for i, s in enumerate(subs, 1))
    update.message.reply_text(text)


# ---------------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    init_db()

    updater    = Updater(TELEGRAM_TOKEN, use_context=True, workers=8)
    dispatcher = updater.dispatcher

    # регистрация /start
    dispatcher.add_handler(registration_handler)

    # отправка домашки
    dispatcher.add_handler(CommandHandler("submit",  submit_cmd))
    dispatcher.add_handler(MessageHandler(Filters.document & ~Filters.command,
                                          handle_document))
    dispatcher.add_handler(CommandHandler("submitted", submitted_cmd))

    # справка
    dispatcher.add_handler(CommandHandler("help", help_cmd))

    # запуск
    updater.start_polling()
    logger.info("Bot is up…")
    updater.idle()


if __name__ == "__main__":
    main()
