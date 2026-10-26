from datetime import datetime
from zoneinfo import ZoneInfo

from . import config


def simdi() -> datetime:
    """Okulun yerel saati (saat dilimi bilgisi olmadan)."""
    return datetime.now(ZoneInfo(config.SAAT_DILIMI)).replace(tzinfo=None, microsecond=0)
