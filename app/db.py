from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import config
from .models import Base


def url_duzelt(url: str) -> str:
    """Bulut sağlayıcıların verdiği postgres:// adreslerini SQLAlchemy/psycopg biçimine çevirir."""
    for eski in ("postgres://", "postgresql://"):
        if url.startswith(eski):
            return "postgresql+psycopg://" + url[len(eski):]
    return url


def motor_olustur(url: str | None = None):
    url = url_duzelt(url or config.DATABASE_URL)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Sunucusuz veritabanları boşta bağlantıyı kapatır: kullanmadan önce sına, düzenli yenile
    return create_engine(url, pool_pre_ping=True, pool_recycle=240)


def tablolari_olustur(engine) -> None:
    Base.metadata.create_all(engine)


def oturum_fabrikasi(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
