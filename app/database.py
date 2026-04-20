"""
Configuración de base de datos - SQLAlchemy engine, session y clase base
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def init_db(database_url: str, echo: bool = False, create_tables: bool = True):
    """Inicializa el engine, la session factory y crea las tablas si faltan."""
    global engine, SessionLocal
    engine = create_engine(database_url, echo=echo)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    if create_tables:
        # Import perezoso para registrar los modelos en Base.metadata
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency que provee una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
