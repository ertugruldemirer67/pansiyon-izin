import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import zaman
from app.main import create_app
from app.models import Kullanici, Ogrenci, VeliOgrenci
from app.security import sifre_hashle

SIFRE = "gizli-sifre-1"
SIMDI = datetime(2026, 11, 6, 12, 0)  # cuma


class Saat:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def saat(monkeypatch):
    s = Saat(SIMDI)
    monkeypatch.setattr(zaman, "simdi", s)
    return s


@pytest.fixture
def uygulama(tmp_path, saat):
    url = os.environ.get("TEST_DATABASE_URL")  # verilirse testler PostgreSQL'e karşı koşar
    if url:
        from app.db import motor_olustur
        from app.models import Base
        motor = motor_olustur(url)
        Base.metadata.drop_all(motor)
        motor.dispose()
        return create_app(url)
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def db(uygulama):
    with uygulama.state.oturum_fabrikasi() as d:
        yield d


@pytest.fixture
def veri(db):
    def kul(ad, rol):
        k = Kullanici(kullanici_adi=ad, ad_soyad=ad.title(), rol=rol,
                      sifre_hash=sifre_hashle(SIFRE))
        db.add(k)
        db.flush()
        return k

    yonetici, belletmen = kul("yonetici1", "yonetici"), kul("belletmen1", "belletmen")
    veli, veli2 = kul("veli1", "veli"), kul("veli2", "veli")
    ogr_kul, ogr2_kul = kul("1001", "ogrenci"), kul("1002", "ogrenci")
    ogr = Ogrenci(kullanici_id=ogr_kul.id, okul_no="1001", ad_soyad="Ali Veli",
                  sinif="10-A", oda="12", qr_token="qr-ali")
    ogr2 = Ogrenci(kullanici_id=ogr2_kul.id, okul_no="1002", ad_soyad="Can Er",
                   sinif="9-B", oda="7", qr_token="qr-can")
    db.add_all([ogr, ogr2])
    db.flush()
    db.add_all([VeliOgrenci(veli_id=veli.id, ogrenci_id=ogr.id, yakinlik="anne"),
                VeliOgrenci(veli_id=veli2.id, ogrenci_id=ogr2.id, yakinlik="baba")])
    db.commit()
    return {"ogrenci": ogr, "ogrenci2": ogr2}


@pytest.fixture
def istemci(uygulama, veri):
    """Her rol için ayrı oturumlu istemciler üretir."""
    istemciler = {}

    def al(kullanici_adi):
        if kullanici_adi not in istemciler:
            c = TestClient(uygulama)
            r = c.post("/auth/giris", json={"kullanici_adi": kullanici_adi, "sifre": SIFRE})
            assert r.status_code == 200, r.text
            istemciler[kullanici_adi] = c
        return istemciler[kullanici_adi]

    return al
