from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLLER = ("veli", "ogrenci", "belletmen", "yonetici", "sistem_yoneticisi")
TURLER = ("evci", "mazeret", "saglik", "ozel")


class Base(DeclarativeBase):
    pass


class Kullanici(Base):
    __tablename__ = "kullanici"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_adi: Mapped[str] = mapped_column(String(64), unique=True)
    ad_soyad: Mapped[str] = mapped_column(String(128))
    rol: Mapped[str] = mapped_column(String(32))
    eposta: Mapped[str | None] = mapped_column(String(128), default=None)
    sifre_hash: Mapped[str | None] = mapped_column(String(128), default=None)
    kayit_kodu_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    aktif: Mapped[bool] = mapped_column(default=True)


class Ogrenci(Base):
    __tablename__ = "ogrenci"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_id: Mapped[int | None] = mapped_column(
        ForeignKey("kullanici.id"), unique=True, default=None
    )
    okul_no: Mapped[str] = mapped_column(String(32), unique=True)
    ad_soyad: Mapped[str] = mapped_column(String(128))
    sinif: Mapped[str] = mapped_column(String(16), default="")
    oda: Mapped[str] = mapped_column(String(16), default="")
    qr_token: Mapped[str] = mapped_column(String(64), unique=True)


class VeliOgrenci(Base):
    __tablename__ = "veli_ogrenci"

    veli_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"), primary_key=True)
    ogrenci_id: Mapped[int] = mapped_column(ForeignKey("ogrenci.id"), primary_key=True)
    yakinlik: Mapped[str] = mapped_column(String(32), default="")


class IzinTalebi(Base):
    __tablename__ = "izin_talebi"

    id: Mapped[int] = mapped_column(primary_key=True)
    ogrenci_id: Mapped[int] = mapped_column(ForeignKey("ogrenci.id"), index=True)
    acan_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    tur: Mapped[str] = mapped_column(String(16))
    cikis_zamani: Mapped[datetime]
    donus_zamani: Mapped[datetime]
    gidecegi_yer: Mapped[str] = mapped_column(String(256), default="")
    gerekce: Mapped[str] = mapped_column(Text, default="")
    durum: Mapped[str] = mapped_column(String(24), index=True)
    olusturma_zamani: Mapped[datetime]


class OnayAdimi(Base):
    __tablename__ = "onay_adimi"

    id: Mapped[int] = mapped_column(primary_key=True)
    talep_id: Mapped[int] = mapped_column(ForeignKey("izin_talebi.id"), index=True)
    adim: Mapped[str] = mapped_column(String(16))  # veli | yonetici
    karar: Mapped[str] = mapped_column(String(8))  # onay | red
    karar_veren_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    aciklama: Mapped[str] = mapped_column(Text, default="")
    yontem: Mapped[str] = mapped_column(String(16), default="panel")  # panel | manuel | acil
    zaman: Mapped[datetime]


class Hareket(Base):
    __tablename__ = "hareket"

    id: Mapped[int] = mapped_column(primary_key=True)
    talep_id: Mapped[int] = mapped_column(ForeignKey("izin_talebi.id"), index=True)
    tip: Mapped[str] = mapped_column(String(8))  # cikis | giris
    zaman: Mapped[datetime]
    belletmen_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    aciklama: Mapped[str] = mapped_column(Text, default="")


class Bildirim(Base):
    __tablename__ = "bildirim"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"), index=True)
    talep_id: Mapped[int | None] = mapped_column(ForeignKey("izin_talebi.id"), default=None)
    icerik: Mapped[str] = mapped_column(Text)
    okundu: Mapped[bool] = mapped_column(default=False)
    zaman: Mapped[datetime]


class Denetim(Base):
    __tablename__ = "denetim"

    id: Mapped[int] = mapped_column(primary_key=True)
    kullanici_id: Mapped[int | None] = mapped_column(ForeignKey("kullanici.id"), default=None)
    islem: Mapped[str] = mapped_column(String(64))
    nesne: Mapped[str] = mapped_column(String(64), default="")
    detay: Mapped[str] = mapped_column(Text, default="")
    zaman: Mapped[datetime]


class Ayar(Base):
    __tablename__ = "ayar"

    anahtar: Mapped[str] = mapped_column(String(64), primary_key=True)
    deger: Mapped[str] = mapped_column(Text)  # JSON
