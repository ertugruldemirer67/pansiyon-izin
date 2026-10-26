import os
import secrets

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./pansiyon.db")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
OTURUM_SAAT = int(os.environ.get("OTURUM_SAAT", "12"))
TOLERANS_DAKIKA = int(os.environ.get("TOLERANS_DAKIKA", "30"))
VELI_ZAMAN_ASIMI_SAAT = int(os.environ.get("VELI_ZAMAN_ASIMI_SAAT", "48"))
SAAT_DILIMI = os.environ.get("SAAT_DILIMI", "Europe/Istanbul")
