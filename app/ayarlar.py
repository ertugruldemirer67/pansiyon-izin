"""Yönetici tarafından değiştirilebilen kurallar (veritabanında saklanır)."""
import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from . import config
from .models import Ayar

GUNLER = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
_SAAT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

VARSAYILAN = {
    # Evci olarak izin verilen aralıklar. Boş liste = zaman kısıtı yok.
    # Her öğe: {"cikis_gun": 4, "cikis_saat": "17:00", "donus_gun": 6, "donus_saat": "20:00"}
    # gün: 0=Pazartesi ... 6=Pazar
    "evci_pencereleri": [],
    # Takvim ayı başına evci talebi sayısı. 0 = sınırsız.
    "aylik_evci_hakki": 0,
    "tolerans_dakika": config.TOLERANS_DAKIKA,
    "veli_zaman_asimi_saat": config.VELI_ZAMAN_ASIMI_SAAT,
    "okul_adi": "Pansiyon",
}


class AyarHatasi(ValueError):
    pass


def _dogrula(anahtar: str, deger):
    if anahtar == "evci_pencereleri":
        if not isinstance(deger, list) or len(deger) > 14:
            raise AyarHatasi("evci_pencereleri en fazla 14 aralıktan oluşan liste olmalı")
        temiz = []
        for p in deger:
            try:
                cg, dg = int(p["cikis_gun"]), int(p["donus_gun"])
                cs, ds = str(p["cikis_saat"]), str(p["donus_saat"])
            except (KeyError, TypeError, ValueError):
                raise AyarHatasi("Aralık biçimi hatalı")
            if not (0 <= cg <= 6 and 0 <= dg <= 6):
                raise AyarHatasi("Gün 0-6 arasında olmalı")
            if not (_SAAT.match(cs) and _SAAT.match(ds)):
                raise AyarHatasi("Saat SS:DD biçiminde olmalı")
            temiz.append({"cikis_gun": cg, "cikis_saat": cs, "donus_gun": dg, "donus_saat": ds})
        return temiz
    if anahtar in ("aylik_evci_hakki", "tolerans_dakika", "veli_zaman_asimi_saat"):
        try:
            n = int(deger)
        except (TypeError, ValueError):
            raise AyarHatasi(f"{anahtar} sayı olmalı")
        ust = {"aylik_evci_hakki": 31, "tolerans_dakika": 240, "veli_zaman_asimi_saat": 720}[anahtar]
        if not 0 <= n <= ust:
            raise AyarHatasi(f"{anahtar} 0-{ust} arasında olmalı")
        return n
    if anahtar == "okul_adi":
        if not isinstance(deger, str) or not deger.strip() or len(deger) > 80:
            raise AyarHatasi("okul_adi 1-80 karakter olmalı")
        return deger.strip()
    raise AyarHatasi(f"Bilinmeyen ayar: {anahtar}")


def hepsi(db: Session) -> dict:
    sonuc = dict(VARSAYILAN)
    for a in db.query(Ayar).all():
        if a.anahtar in VARSAYILAN:
            sonuc[a.anahtar] = json.loads(a.deger)
    return sonuc


def al(db: Session, anahtar: str):
    return hepsi(db)[anahtar]


def guncelle(db: Session, degerler: dict) -> dict:
    for anahtar, deger in degerler.items():
        temiz = _dogrula(anahtar, deger)
        kayit = db.get(Ayar, anahtar)
        if kayit is None:
            db.add(Ayar(anahtar=anahtar, deger=json.dumps(temiz, ensure_ascii=False)))
        else:
            kayit.deger = json.dumps(temiz, ensure_ascii=False)
    db.flush()
    return hepsi(db)


# --- evci kuralı -------------------------------------------------------------

def _hafta_dakikasi(gun: int, saat: str) -> int:
    s, d = saat.split(":")
    return gun * 1440 + int(s) * 60 + int(d)


def _hafta_dakikasi_dt(t: datetime) -> int:
    return t.weekday() * 1440 + t.hour * 60 + t.minute


def pencereye_uyar_mi(pencere: dict, cikis: datetime, donus: datetime) -> bool:
    """Çıkış ve dönüş aynı izinli aralığın içinde mi? Aralık haftayı aşabilir (Cuma→Pazar)."""
    bas = _hafta_dakikasi(pencere["cikis_gun"], pencere["cikis_saat"])
    bit = _hafta_dakikasi(pencere["donus_gun"], pencere["donus_saat"])
    if bit <= bas:
        bit += 7 * 1440  # hafta sonuna sarkan aralık
    uzunluk = bit - bas
    sure = (donus - cikis).total_seconds() / 60

    # çıkışın aralığın başından itibaren ne kadar sonra olduğu (haftalık sarmal)
    ofset = (_hafta_dakikasi_dt(cikis) - bas) % (7 * 1440)
    return ofset + sure <= uzunluk


def evci_kuralini_denetle(ayar: dict, cikis: datetime, donus: datetime) -> str | None:
    """Kural ihlalinde kullanıcıya gösterilecek mesajı döndürür, uygunsa None."""
    pencereler = ayar["evci_pencereleri"]
    if not pencereler:
        return None
    if any(pencereye_uyar_mi(p, cikis, donus) for p in pencereler):
        return None
    izinli = "; ".join(
        f"{GUNLER[p['cikis_gun']]} {p['cikis_saat']} – {GUNLER[p['donus_gun']]} {p['donus_saat']}"
        for p in pencereler)
    return f"Evci yalnızca şu aralıklarda alınabilir: {izinli}"
