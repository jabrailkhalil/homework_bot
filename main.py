import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Google Drive API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Импорт приватных данных из отдельного файла
from private_config import TELEGRAM_TOKEN, GOOGLE_CLIENT_SECRET_FILE, GOOGLE_TOKEN_FILE, GOOGLE_SCOPES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_file_to_drive(file_path, file_name, mime_type):
    """
    Загружает файл на Google Drive.
    Возвращает ID загруженного файла.
    """
    creds = None

    # Если существует файл с токеном, пробуем загрузить сохранённые токены
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)

    # Если токенов нет или они недействительны – запускаем OAuth-аутентификацию
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRET_FILE, GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Сохраняем токены для следующего запуска
        with open(GOOGLE_TOKEN_FILE, 'w') as token_file:
            token_file.write(creds.to_json())

    # Создаем клиент для Google Drive API
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file_name}
    media = MediaFileUpload(file_path, mimetype=mime_type)
    uploaded_file = service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()

    return uploaded_file.get('id')

def handle_file_upload(update: Update, context: CallbackContext):
    try:
        if update.message.document:
            document = update.message.document
            file_name = document.file_name
            # Создаем временную папку, если её нет
            temp_dir = 'temp'
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            local_path = os.path.join(temp_dir, file_name)

            # Скачиваем файл из Telegram во временную папку
            file_id = document.file_id
            new_file = context.bot.get_file(file_id)
            new_file.download(custom_path=local_path)
            logger.info("Файл %s временно сохранён по пути %s", file_name, os.path.abspath(local_path))

            # Определяем MIME-тип (если не указан, используем 'application/octet-stream')
            mime_type = document.mime_type or 'application/octet-stream'

            # Загружаем файл на Google Drive
            drive_file_id = upload_file_to_drive(local_path, file_name, mime_type)
            update.message.reply_text(
                f"Файл '{file_name}' успешно загружен на Google Drive.\nID файла: {drive_file_id}"
            )

            # Удаляем временный файл
            os.remove(local_path)
        else:
            update.message.reply_text("Нет документа для загрузки.")
    except Exception as e:
        logger.error("Ошибка при обработке файла: %s", e)
        update.message.reply_text("Произошла ошибка при загрузке файла на Google Drive.")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Отправь мне документ, и я загружу его на Google Drive.")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document, handle_file_upload))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
