# database/db_init.py
from .models import Base, engine

def init_db():
    print("Initializing database...")
    # Создает таблицы, если их нет
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.")

if __name__ == "__main__":
    # Этот блок выполнится, если запустить файл напрямую: python -m database.db_init
    init_db() 