from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import config
from .models import Base


def motor_olustur(url: str | None = None):
    url = url or config.DATABASE_URL
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)


def tablolari_olustur(engine) -> None:
    Base.metadata.create_all(engine)


def oturum_fabrikasi(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
