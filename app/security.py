import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

import bcrypt
from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import config

_KOD_ALFABE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # karışan karakterler yok


def sifre_hashle(sifre: str) -> str:
    return bcrypt.hashpw(sifre.encode()[:72], bcrypt.gensalt()).decode()


def sifre_dogru_mu(sifre: str, hash_: str | None) -> bool:
    if not hash_:
        return False
    return bcrypt.checkpw(sifre.encode()[:72], hash_.encode())


def kayit_kodu_uret() -> str:
    return "".join(secrets.choice(_KOD_ALFABE) for _ in range(10))


def kod_hashle(kod: str) -> str:
    return hashlib.sha256(kod.strip().upper().encode()).hexdigest()


def kod_dogru_mu(kod: str, hash_: str | None) -> bool:
    if not hash_:
        return False
    return hmac.compare_digest(kod_hashle(kod), hash_)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="oturum")


def oturum_jetonu(kullanici_id: int) -> str:
    return _serializer().dumps(kullanici_id)


def jetondan_kullanici_id(jeton: str) -> int | None:
    try:
        return _serializer().loads(jeton, max_age=config.OTURUM_SAAT * 3600)
    except BadSignature:
        return None


class DenemeSiniri:
    """Kullanıcı adı başına başarısız deneme sayısını sınırlar (bellek içi)."""

    def __init__(self, limit: int = 5, pencere_sn: int = 900):
        self.limit = limit
        self.pencere = pencere_sn
        self._kayit: dict[str, deque] = defaultdict(deque)

    def _temizle(self, anahtar: str) -> deque:
        q = self._kayit[anahtar]
        sinir = time.monotonic() - self.pencere
        while q and q[0] < sinir:
            q.popleft()
        return q

    def engelli_mi(self, anahtar: str) -> bool:
        return len(self._temizle(anahtar)) >= self.limit

    def basarisiz(self, anahtar: str) -> None:
        self._temizle(anahtar).append(time.monotonic())

    def sifirla(self, anahtar: str) -> None:
        self._kayit.pop(anahtar, None)
