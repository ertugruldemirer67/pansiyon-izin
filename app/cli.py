"""Komut satırı yönetim araçları.

Örnek:
    python -m app.cli kullanici-ekle --kullanici-adi ayse --ad-soyad "Ayşe Yılmaz" --rol yonetici
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from .db import motor_olustur, oturum_fabrikasi, tablolari_olustur
from .models import ROLLER, Kullanici
from .security import sifre_hashle


def kullanici_ekle(args) -> int:
    engine = motor_olustur()
    tablolari_olustur(engine)
    sifre = args.sifre or getpass.getpass("Şifre (en az 8 karakter): ")
    if len(sifre) < 8:
        print("Şifre en az 8 karakter olmalı", file=sys.stderr)
        return 1
    with oturum_fabrikasi(engine)() as db:
        if db.scalars(select(Kullanici).where(
                Kullanici.kullanici_adi == args.kullanici_adi)).first():
            print("Bu kullanıcı adı zaten var", file=sys.stderr)
            return 1
        db.add(Kullanici(kullanici_adi=args.kullanici_adi, ad_soyad=args.ad_soyad,
                         rol=args.rol, eposta=args.eposta, sifre_hash=sifre_hashle(sifre)))
        db.commit()
    print("Kullanıcı eklendi")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="app.cli")
    alt = ap.add_subparsers(dest="komut", required=True)
    k = alt.add_parser("kullanici-ekle", help="Personel hesabı oluşturur")
    k.add_argument("--kullanici-adi", required=True)
    k.add_argument("--ad-soyad", required=True)
    k.add_argument("--rol", required=True, choices=[r for r in ROLLER if r not in ("veli", "ogrenci")])
    k.add_argument("--eposta")
    k.add_argument("--sifre", help="Verilmezse sorulur")
    k.set_defaults(fonk=kullanici_ekle)
    args = ap.parse_args()
    return args.fonk(args)


if __name__ == "__main__":
    raise SystemExit(main())
