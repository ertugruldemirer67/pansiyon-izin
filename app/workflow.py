"""İzin talebi durum makinesi ve iş kuralları."""
import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import (
    TURLER,
    Bildirim,
    Denetim,
    Hareket,
    IzinTalebi,
    Kullanici,
    OnayAdimi,
    Ogrenci,
    VeliOgrenci,
)

VELI_BEKLIYOR = "veli_bekliyor"
YONETICI_BEKLIYOR = "yonetici_bekliyor"
ONAYLANDI = "onaylandi"
DISARIDA = "disarida"
GECIKTI = "gecikti"
DONDU = "dondu"
REDDEDILDI = "reddedildi"
IPTAL = "iptal"
ZAMAN_ASIMI = "zaman_asimi"
KULLANILMADI = "kullanilmadi"

AKTIF = (VELI_BEKLIYOR, YONETICI_BEKLIYOR, ONAYLANDI, DISARIDA, GECIKTI)
DISARIDAKI = (DISARIDA, GECIKTI)


class IsKuraliHatasi(Exception):
    def __init__(self, mesaj: str, kod: int = 409):
        super().__init__(mesaj)
        self.mesaj = mesaj
        self.kod = kod


class Yasak(IsKuraliHatasi):
    def __init__(self, mesaj: str = "Bu işlem için yetkiniz yok"):
        super().__init__(mesaj, 403)


class Bulunamadi(IsKuraliHatasi):
    def __init__(self, mesaj: str = "Kayıt bulunamadı"):
        super().__init__(mesaj, 404)


# --- yardımcılar -----------------------------------------------------------

def denetle(db: Session, kullanici_id: int | None, islem: str, nesne: str = "",
            detay: dict | None = None, now: datetime | None = None) -> None:
    from .zaman import simdi

    db.add(Denetim(
        kullanici_id=kullanici_id, islem=islem, nesne=nesne,
        detay=json.dumps(detay or {}, ensure_ascii=False, default=str),
        zaman=now or simdi(),
    ))


def bildir(db: Session, kullanici_idleri, icerik: str, talep_id: int | None,
           now: datetime) -> None:
    for kid in set(kullanici_idleri):
        db.add(Bildirim(kullanici_id=kid, talep_id=talep_id, icerik=icerik, zaman=now))


def veli_idleri(db: Session, ogrenci_id: int) -> list[int]:
    return list(db.scalars(
        select(VeliOgrenci.veli_id).where(VeliOgrenci.ogrenci_id == ogrenci_id)
    ))


def yonetici_idleri(db: Session) -> list[int]:
    return list(db.scalars(
        select(Kullanici.id).where(Kullanici.rol == "yonetici", Kullanici.aktif.is_(True))
    ))


def veli_mi(db: Session, kullanici: Kullanici, ogrenci_id: int) -> bool:
    return kullanici.rol == "veli" and kullanici.id in veli_idleri(db, ogrenci_id)


def talep_getir(db: Session, talep_id: int) -> IzinTalebi:
    talep = db.get(IzinTalebi, talep_id)
    if talep is None:
        raise Bulunamadi("Talep bulunamadı")
    return talep


def talebi_gorebilir_mi(db: Session, kullanici: Kullanici, talep: IzinTalebi) -> bool:
    if kullanici.rol in ("yonetici", "belletmen"):
        return True
    if kullanici.rol == "veli":
        return veli_mi(db, kullanici, talep.ogrenci_id)
    if kullanici.rol == "ogrenci":
        ogr = db.get(Ogrenci, talep.ogrenci_id)
        return ogr is not None and ogr.kullanici_id == kullanici.id
    return False


def _ogrenci_ad(db: Session, ogrenci_id: int) -> str:
    ogr = db.get(Ogrenci, ogrenci_id)
    return ogr.ad_soyad if ogr else "?"


# --- talep açma ------------------------------------------------------------

def talep_ac(db: Session, kullanici: Kullanici, *, ogrenci_id: int, tur: str,
             cikis: datetime, donus: datetime, yer: str, gerekce: str,
             now: datetime) -> IzinTalebi:
    if tur not in TURLER:
        raise IsKuraliHatasi(f"Geçersiz tür: {tur}", 422)
    if donus <= cikis:
        raise IsKuraliHatasi("Dönüş zamanı çıkıştan sonra olmalı", 422)
    if donus <= now:
        raise IsKuraliHatasi("Dönüş zamanı geçmişte olamaz", 422)

    ogrenci = db.get(Ogrenci, ogrenci_id)
    if ogrenci is None:
        raise Bulunamadi("Öğrenci bulunamadı")

    if kullanici.rol == "veli":
        if not veli_mi(db, kullanici, ogrenci_id):
            raise Yasak("Bu öğrenci için talep açamazsınız")
        durum = YONETICI_BEKLIYOR
    elif kullanici.rol == "ogrenci":
        if ogrenci.kullanici_id != kullanici.id:
            raise Yasak("Yalnızca kendiniz için talep açabilirsiniz")
        durum = VELI_BEKLIYOR
    elif kullanici.rol == "yonetici":
        if not gerekce.strip():
            raise IsKuraliHatasi("Acil izin için gerekçe zorunlu", 422)
        durum = ONAYLANDI
    else:
        raise Yasak()

    cakisan = db.scalars(
        select(IzinTalebi).where(
            IzinTalebi.ogrenci_id == ogrenci_id,
            IzinTalebi.durum.in_(AKTIF),
            IzinTalebi.cikis_zamani < donus,
            IzinTalebi.donus_zamani > cikis,
        )
    ).first()
    if cakisan is not None:
        raise IsKuraliHatasi(f"Bu aralıkta zaten bir talep var (#{cakisan.id})")

    talep = IzinTalebi(
        ogrenci_id=ogrenci_id, acan_id=kullanici.id, tur=tur,
        cikis_zamani=cikis, donus_zamani=donus, gidecegi_yer=yer.strip(),
        gerekce=gerekce.strip(), durum=durum, olusturma_zamani=now,
    )
    db.add(talep)
    db.flush()

    ad = ogrenci.ad_soyad
    if kullanici.rol == "veli":
        db.add(OnayAdimi(talep_id=talep.id, adim="veli", karar="onay",
                         karar_veren_id=kullanici.id, aciklama="Veli talebi açtı",
                         yontem="panel", zaman=now))
        bildir(db, yonetici_idleri(db), f"{ad} için yeni izin talebi onay bekliyor", talep.id, now)
    elif kullanici.rol == "ogrenci":
        bildir(db, veli_idleri(db, ogrenci_id), f"{ad} izin talebi açtı, onayınız bekleniyor",
               talep.id, now)
    else:
        db.add(OnayAdimi(talep_id=talep.id, adim="yonetici", karar="onay",
                         karar_veren_id=kullanici.id, aciklama=gerekce.strip(),
                         yontem="acil", zaman=now))
        bildir(db, veli_idleri(db, ogrenci_id), f"{ad} için acil izin verildi", talep.id, now)

    denetle(db, kullanici.id, "talep_ac", f"talep:{talep.id}",
            {"durum": durum, "tur": tur}, now)
    return talep


# --- kararlar --------------------------------------------------------------

def veli_karar(db: Session, kullanici: Kullanici, talep: IzinTalebi, *, onay: bool,
               aciklama: str, now: datetime) -> IzinTalebi:
    if talep.durum != VELI_BEKLIYOR:
        raise IsKuraliHatasi("Talep veli onayı beklemiyor")

    if kullanici.rol == "veli":
        if not veli_mi(db, kullanici, talep.ogrenci_id):
            raise Yasak("Bu öğrencinin velisi değilsiniz")
        yontem = "panel"
    elif kullanici.rol == "yonetici":
        if not aciklama.strip():
            raise IsKuraliHatasi("Manuel onayda açıklama zorunlu (ör. telefonla onay alındı)", 422)
        yontem = "manuel"
    else:
        raise Yasak()

    db.add(OnayAdimi(talep_id=talep.id, adim="veli", karar="onay" if onay else "red",
                     karar_veren_id=kullanici.id, aciklama=aciklama.strip(),
                     yontem=yontem, zaman=now))
    ad = _ogrenci_ad(db, talep.ogrenci_id)
    if onay:
        talep.durum = YONETICI_BEKLIYOR
        bildir(db, yonetici_idleri(db), f"{ad} için talep veli onayından geçti", talep.id, now)
    else:
        talep.durum = REDDEDILDI
        bildir(db, [talep.acan_id], f"{ad} için talep veli tarafından reddedildi", talep.id, now)
    denetle(db, kullanici.id, "veli_karar", f"talep:{talep.id}",
            {"onay": onay, "yontem": yontem}, now)
    return talep


def yonetici_karar(db: Session, kullanici: Kullanici, talep: IzinTalebi, *, onay: bool,
                   aciklama: str, now: datetime) -> IzinTalebi:
    if kullanici.rol != "yonetici":
        raise Yasak()
    if talep.durum != YONETICI_BEKLIYOR:
        raise IsKuraliHatasi("Talep yönetici onayı beklemiyor")
    if not onay and not aciklama.strip():
        raise IsKuraliHatasi("Red için gerekçe zorunlu", 422)

    db.add(OnayAdimi(talep_id=talep.id, adim="yonetici", karar="onay" if onay else "red",
                     karar_veren_id=kullanici.id, aciklama=aciklama.strip(),
                     yontem="panel", zaman=now))
    ad = _ogrenci_ad(db, talep.ogrenci_id)
    alicilar = set(veli_idleri(db, talep.ogrenci_id)) | {talep.acan_id}
    if onay:
        talep.durum = ONAYLANDI
        bildir(db, alicilar, f"{ad} için izin talebi onaylandı", talep.id, now)
    else:
        talep.durum = REDDEDILDI
        bildir(db, alicilar, f"{ad} için izin talebi reddedildi: {aciklama.strip()}", talep.id, now)
    denetle(db, kullanici.id, "yonetici_karar", f"talep:{talep.id}", {"onay": onay}, now)
    return talep


def iptal(db: Session, kullanici: Kullanici, talep: IzinTalebi, *, now: datetime) -> IzinTalebi:
    if talep.durum not in (VELI_BEKLIYOR, YONETICI_BEKLIYOR, ONAYLANDI):
        raise IsKuraliHatasi("Bu aşamadaki talep iptal edilemez")
    yetkili = (
        kullanici.rol == "yonetici"
        or kullanici.id == talep.acan_id
        or veli_mi(db, kullanici, talep.ogrenci_id)
    )
    if not yetkili:
        raise Yasak()
    talep.durum = IPTAL
    ad = _ogrenci_ad(db, talep.ogrenci_id)
    bildir(db, (set(veli_idleri(db, talep.ogrenci_id)) | {talep.acan_id}) - {kullanici.id},
           f"{ad} için izin talebi iptal edildi", talep.id, now)
    denetle(db, kullanici.id, "iptal", f"talep:{talep.id}", {}, now)
    return talep


# --- çıkış / giriş ---------------------------------------------------------

def okut(db: Session, kullanici: Kullanici, qr_token: str, *, now: datetime) -> dict:
    if kullanici.rol not in ("belletmen", "yonetici"):
        raise Yasak()
    ogrenci = db.scalars(select(Ogrenci).where(Ogrenci.qr_token == qr_token)).first()
    if ogrenci is None:
        raise Bulunamadi("Geçersiz QR kodu")

    disarida = db.scalars(
        select(IzinTalebi).where(IzinTalebi.ogrenci_id == ogrenci.id,
                                 IzinTalebi.durum.in_(DISARIDAKI))
    ).first()
    if disarida is not None:
        gec = now > disarida.donus_zamani + timedelta(minutes=config.TOLERANS_DAKIKA)
        disarida.durum = DONDU
        db.add(Hareket(talep_id=disarida.id, tip="giris", zaman=now,
                       belletmen_id=kullanici.id,
                       aciklama="geç dönüş" if gec else ""))
        denetle(db, kullanici.id, "giris", f"talep:{disarida.id}", {"gec": gec}, now)
        return {"tip": "giris", "gec": gec, "ogrenci": ogrenci.ad_soyad, "talep_id": disarida.id}

    tolerans = timedelta(minutes=config.TOLERANS_DAKIKA)
    onayli = list(db.scalars(
        select(IzinTalebi).where(IzinTalebi.ogrenci_id == ogrenci.id,
                                 IzinTalebi.durum == ONAYLANDI)
    ))
    for talep in onayli:
        if talep.cikis_zamani - tolerans <= now <= talep.donus_zamani:
            talep.durum = DISARIDA
            db.add(Hareket(talep_id=talep.id, tip="cikis", zaman=now,
                           belletmen_id=kullanici.id))
            denetle(db, kullanici.id, "cikis", f"talep:{talep.id}", {}, now)
            return {"tip": "cikis", "gec": False, "ogrenci": ogrenci.ad_soyad,
                    "talep_id": talep.id}

    if onayli:
        raise IsKuraliHatasi(
            f"{ogrenci.ad_soyad}: onaylı izin var ama şu an çıkış saati içinde değil")
    raise IsKuraliHatasi(f"{ogrenci.ad_soyad}: geçerli onaylı izin yok")


def tara(db: Session, now: datetime) -> dict:
    """Süre aşımlarını işaretler: geç kalanlar, yanıtsız veli onayları, kullanılmayan izinler."""
    sonuc = {"gecikti": 0, "zaman_asimi": 0, "kullanilmadi": 0}

    sinir = now - timedelta(minutes=config.TOLERANS_DAKIKA)
    for talep in db.scalars(select(IzinTalebi).where(
            IzinTalebi.durum == DISARIDA, IzinTalebi.donus_zamani < sinir)):
        talep.durum = GECIKTI
        ad = _ogrenci_ad(db, talep.ogrenci_id)
        bildir(db, set(veli_idleri(db, talep.ogrenci_id)) | set(yonetici_idleri(db)),
               f"{ad} planlanan dönüş saatini geçti", talep.id, now)
        denetle(db, None, "gecikti", f"talep:{talep.id}", {}, now)
        sonuc["gecikti"] += 1

    veli_siniri = now - timedelta(hours=config.VELI_ZAMAN_ASIMI_SAAT)
    for talep in db.scalars(select(IzinTalebi).where(
            IzinTalebi.durum == VELI_BEKLIYOR, IzinTalebi.olusturma_zamani < veli_siniri)):
        talep.durum = ZAMAN_ASIMI
        ad = _ogrenci_ad(db, talep.ogrenci_id)
        bildir(db, set(yonetici_idleri(db)) | {talep.acan_id},
               f"{ad} için veli onayı zaman aşımına uğradı", talep.id, now)
        denetle(db, None, "zaman_asimi", f"talep:{talep.id}", {}, now)
        sonuc["zaman_asimi"] += 1

    for talep in db.scalars(select(IzinTalebi).where(
            IzinTalebi.durum == ONAYLANDI, IzinTalebi.donus_zamani < now)):
        talep.durum = KULLANILMADI
        denetle(db, None, "kullanilmadi", f"talep:{talep.id}", {}, now)
        sonuc["kullanilmadi"] += 1

    return sonuc
