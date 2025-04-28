# database/crud.py
# Здесь будут функции для создания, чтения, обновления, удаления (CRUD) данных.

from sqlalchemy.orm import Session
from . import models

def get_user(db: Session, user_id: int):
    """Получает пользователя по его Telegram ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, user_id: int, full_name: str, username: str | None):
    """Создает нового пользователя в базе данных."""
    db_user = models.User(id=user_id, username=username, full_name=full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Другие CRUD функции будут добавляться сюда по мере необходимости
# (для предметов, домашних заданий, статусов сдачи и т.д.)

# Пример (добавим позже):
# def get_user(db: Session, user_id: int):
#     return db.query(models.User).filter(models.User.id == user_id).first() 