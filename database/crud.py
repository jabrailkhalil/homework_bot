# database/crud.py
# Здесь будут функции для создания, чтения, обновления, удаления (CRUD) данных.

from sqlalchemy.orm import Session
from . import models

# Пример (добавим позже):
# def get_user(db: Session, user_id: int):
#     return db.query(models.User).filter(models.User.id == user_id).first() 