from datetime import datetime

import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ayarlar, config, importer, workflow, zaman
from .db import motor_olustur, oturum_fabrikasi, tablolari_olustur
from .deps import get_db, mevcut_kullanici, rol_gerekli
from .models import (
    Bildirim,
    Hareket,
    IzinTalebi,
    Kullanici,
    OnayAdimi,
    Ogrenci,
    VeliOgrenci,
)
from .security import (
    DenemeSiniri,
    kayit_kodu_uret,
    kod_hashle,
    kod_dogru_mu,
    oturum_jetonu,
    sifre_dogru_mu,
    sifre_hashle,
)


class GirisIstegi(BaseModel):
    kullanici_adi: str
    sifre: str


class IlkKayitIstegi(BaseModel):
    kullanici_adi: str
    kod: str
    sifre: str = Field(min_length=8, max_length=72)


class TalepIstegi(BaseModel):
    ogrenci_id: int
    tur: str
    cikis_zamani: datetime
    donus_zamani: datetime
    gidecegi_yer: str = ""
    gerekce: str = ""


class KararIstegi(BaseModel):
    onay: bool
    aciklama: str = ""


class OkutIstegi(BaseModel):
    qr_token: str | None = None
    okul_no: str | None = None


class TopluKararIstegi(BaseModel):
    idler: list[int] = Field(min_length=1, max_length=200)
    onay: bool
    aciklama: str = ""


class PersonelIstegi(BaseModel):
    kullanici_adi: str = Field(min_length=3, max_length=64)
    ad_soyad: str = Field(min_length=2, max_length=128)
    rol: str
    eposta: str | None = None


def kullanici_dict(k: Kullanici) -> dict:
    return {"id": k.id, "kullanici_adi": k.kullanici_adi, "ad_soyad": k.ad_soyad, "rol": k.rol}


def talep_dict(db: Session, t: IzinTalebi) -> dict:
    ogr = db.get(Ogrenci, t.ogrenci_id)
    adimlar = db.scalars(
        select(OnayAdimi).where(OnayAdimi.talep_id == t.id).order_by(OnayAdimi.id))
    hareketler = db.scalars(
        select(Hareket).where(Hareket.talep_id == t.id).order_by(Hareket.id))
    veliler = db.execute(
        select(Kullanici.ad_soyad, Kullanici.kullanici_adi, VeliOgrenci.yakinlik)
        .join(VeliOgrenci, VeliOgrenci.veli_id == Kullanici.id)
        .where(VeliOgrenci.ogrenci_id == t.ogrenci_id).order_by(Kullanici.id))
    return {
        "id": t.id,
        "acan_id": t.acan_id,
        "ogrenci": {"id": ogr.id, "ad_soyad": ogr.ad_soyad, "sinif": ogr.sinif, "oda": ogr.oda,
                    "okul_no": ogr.okul_no},
        "veliler": [{"ad_soyad": v.ad_soyad, "telefon": v.kullanici_adi, "yakinlik": v.yakinlik}
                    for v in veliler],
        "tur": t.tur,
        "cikis_zamani": t.cikis_zamani,
        "donus_zamani": t.donus_zamani,
        "gidecegi_yer": t.gidecegi_yer,
        "gerekce": t.gerekce,
        "durum": t.durum,
        "olusturma_zamani": t.olusturma_zamani,
        "onaylar": [{"adim": a.adim, "karar": a.karar, "yontem": a.yontem,
                     "aciklama": a.aciklama, "zaman": a.zaman} for a in adimlar],
        "hareketler": [{"tip": h.tip, "zaman": h.zaman, "aciklama": h.aciklama}
                       for h in hareketler],
    }


def ilk_yonetici_olustur(fabrika) -> None:
    """Kabuk erişimi olmayan ortamlar için: ortam değişkenlerinden ilk sistem yöneticisini açar.

    Yalnızca hiç sistem yöneticisi yokken çalışır. Hesap oluştuktan sonra
    ILK_YONETICI_SIFRE değişkenini silmeniz önerilir."""
    ad, sifre = os.environ.get("ILK_YONETICI_ADI"), os.environ.get("ILK_YONETICI_SIFRE")
    if not ad or not sifre:
        return
    if len(sifre) < 8:
        raise RuntimeError("ILK_YONETICI_SIFRE en az 8 karakter olmalı")
    with fabrika() as db:
        if db.scalars(select(Kullanici).where(Kullanici.rol == "sistem_yoneticisi")).first():
            return
        if db.scalars(select(Kullanici).where(Kullanici.kullanici_adi == ad)).first():
            return
        db.add(Kullanici(kullanici_adi=ad, ad_soyad="Sistem Yöneticisi", rol="sistem_yoneticisi",
                         sifre_hash=sifre_hashle(sifre)))
        db.commit()


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Pansiyon İzin Sistemi")
    engine = motor_olustur(database_url)
    tablolari_olustur(engine)
    app.state.motor = engine
    app.state.oturum_fabrikasi = oturum_fabrikasi(engine)
    app.state.giris_siniri = DenemeSiniri()
    ilk_yonetici_olustur(app.state.oturum_fabrikasi)

    @app.exception_handler(workflow.IsKuraliHatasi)
    async def is_kurali_hatasi(_: Request, e: workflow.IsKuraliHatasi):
        return JSONResponse({"detail": e.mesaj}, status_code=e.kod)

    # --- kimlik doğrulama ---------------------------------------------------

    @app.post("/auth/giris")
    def giris(veri: GirisIstegi, request: Request, response: Response,
              db: Session = Depends(get_db)):
        sinir: DenemeSiniri = request.app.state.giris_siniri
        if sinir.engelli_mi(veri.kullanici_adi):
            raise HTTPException(429, "Çok fazla başarısız deneme, daha sonra tekrar deneyin")
        k = db.scalars(select(Kullanici).where(
            Kullanici.kullanici_adi == veri.kullanici_adi)).first()
        if k is None or not k.aktif or not sifre_dogru_mu(veri.sifre, k.sifre_hash):
            sinir.basarisiz(veri.kullanici_adi)
            raise HTTPException(401, "Kullanıcı adı veya şifre hatalı")
        sinir.sifirla(veri.kullanici_adi)
        jeton = oturum_jetonu(k.id)
        response.set_cookie("oturum", jeton, httponly=True, samesite="lax",
                            secure=config.COOKIE_SECURE, max_age=config.OTURUM_SAAT * 3600)
        return {"jeton": jeton, "kullanici": kullanici_dict(k)}

    @app.post("/auth/ilk-kayit")
    def ilk_kayit(veri: IlkKayitIstegi, request: Request, db: Session = Depends(get_db)):
        sinir: DenemeSiniri = request.app.state.giris_siniri
        if sinir.engelli_mi(veri.kullanici_adi):
            raise HTTPException(429, "Çok fazla başarısız deneme, daha sonra tekrar deneyin")
        k = db.scalars(select(Kullanici).where(
            Kullanici.kullanici_adi == veri.kullanici_adi)).first()
        if k is None or not kod_dogru_mu(veri.kod, k.kayit_kodu_hash):
            sinir.basarisiz(veri.kullanici_adi)
            raise HTTPException(400, "Kullanıcı adı veya kayıt kodu hatalı")
        k.sifre_hash = sifre_hashle(veri.sifre)
        k.kayit_kodu_hash = None
        k.aktif = True
        workflow.denetle(db, k.id, "ilk_kayit", f"kullanici:{k.id}")
        return {"kullanici": kullanici_dict(k)}

    @app.post("/auth/cikis")
    def cikis(response: Response):
        response.delete_cookie("oturum")
        return {"tamam": True}

    @app.get("/ben")
    def ben(k: Kullanici = Depends(mevcut_kullanici), db: Session = Depends(get_db)):
        veri = kullanici_dict(k)
        if k.rol == "veli":
            veri["cocuklar"] = [
                {"id": o.id, "ad_soyad": o.ad_soyad, "sinif": o.sinif, "oda": o.oda}
                for o in db.scalars(select(Ogrenci).join(
                    VeliOgrenci, VeliOgrenci.ogrenci_id == Ogrenci.id
                ).where(VeliOgrenci.veli_id == k.id))
            ]
        elif k.rol == "ogrenci":
            ogr = db.scalars(select(Ogrenci).where(Ogrenci.kullanici_id == k.id)).first()
            if ogr:
                veri["ogrenci"] = {"id": ogr.id, "sinif": ogr.sinif, "oda": ogr.oda,
                                   "qr_token": ogr.qr_token}
        return veri

    # --- talepler -----------------------------------------------------------

    @app.post("/talepler", status_code=201)
    def talep_olustur(veri: TalepIstegi, k: Kullanici = Depends(mevcut_kullanici),
                      db: Session = Depends(get_db)):
        t = workflow.talep_ac(
            db, k, ogrenci_id=veri.ogrenci_id, tur=veri.tur, cikis=veri.cikis_zamani,
            donus=veri.donus_zamani, yer=veri.gidecegi_yer, gerekce=veri.gerekce,
            now=zaman.simdi())
        return talep_dict(db, t)

    @app.get("/talepler")
    def talepleri_listele(durum: str | None = None, ogrenci_id: int | None = None,
                          k: Kullanici = Depends(mevcut_kullanici),
                          db: Session = Depends(get_db)):
        q = select(IzinTalebi).order_by(IzinTalebi.id.desc())
        if k.rol == "veli":
            q = q.where(IzinTalebi.ogrenci_id.in_(
                select(VeliOgrenci.ogrenci_id).where(VeliOgrenci.veli_id == k.id)))
        elif k.rol == "ogrenci":
            q = q.where(IzinTalebi.ogrenci_id.in_(
                select(Ogrenci.id).where(Ogrenci.kullanici_id == k.id)))
        elif k.rol not in ("yonetici", "belletmen"):
            raise HTTPException(403, "Bu işlem için yetkiniz yok")
        if durum:
            q = q.where(IzinTalebi.durum == durum)
        if ogrenci_id:
            q = q.where(IzinTalebi.ogrenci_id == ogrenci_id)
        return [talep_dict(db, t) for t in db.scalars(q.limit(200))]

    @app.get("/talepler/{talep_id}")
    def talep_detay(talep_id: int, k: Kullanici = Depends(mevcut_kullanici),
                    db: Session = Depends(get_db)):
        t = workflow.talep_getir(db, talep_id)
        if not workflow.talebi_gorebilir_mi(db, k, t):
            raise workflow.Yasak()
        return talep_dict(db, t)

    @app.post("/talepler/{talep_id}/veli-karar")
    def veli_karar(talep_id: int, veri: KararIstegi,
                   k: Kullanici = Depends(mevcut_kullanici), db: Session = Depends(get_db)):
        t = workflow.talep_getir(db, talep_id)
        workflow.veli_karar(db, k, t, onay=veri.onay, aciklama=veri.aciklama,
                            now=zaman.simdi())
        return talep_dict(db, t)

    @app.post("/talepler/{talep_id}/yonetici-karar")
    def yonetici_karar(talep_id: int, veri: KararIstegi,
                       k: Kullanici = Depends(mevcut_kullanici),
                       db: Session = Depends(get_db)):
        t = workflow.talep_getir(db, talep_id)
        workflow.yonetici_karar(db, k, t, onay=veri.onay, aciklama=veri.aciklama,
                                now=zaman.simdi())
        return talep_dict(db, t)

    @app.post("/talepler/{talep_id}/iptal")
    def talep_iptal(talep_id: int, k: Kullanici = Depends(mevcut_kullanici),
                    db: Session = Depends(get_db)):
        t = workflow.talep_getir(db, talep_id)
        workflow.iptal(db, k, t, now=zaman.simdi())
        return talep_dict(db, t)

    # --- çıkış / giriş ------------------------------------------------------

    @app.post("/hareket/okut")
    def okut(veri: OkutIstegi, k: Kullanici = Depends(mevcut_kullanici),
             db: Session = Depends(get_db)):
        return workflow.okut(db, k, veri.qr_token, okul_no=veri.okul_no, now=zaman.simdi())

    def _disaridakiler(db: Session, durumlar):
        workflow.tara(db, zaman.simdi())
        db.flush()
        q = select(IzinTalebi).where(IzinTalebi.durum.in_(durumlar)).order_by(
            IzinTalebi.donus_zamani)
        return [talep_dict(db, t) for t in db.scalars(q)]

    @app.get("/disaridakiler")
    def disaridakiler(_: Kullanici = Depends(rol_gerekli("belletmen", "yonetici")),
                      db: Session = Depends(get_db)):
        return _disaridakiler(db, workflow.DISARIDAKI)

    @app.get("/gecikenler")
    def gecikenler(_: Kullanici = Depends(rol_gerekli("belletmen", "yonetici")),
                   db: Session = Depends(get_db)):
        return _disaridakiler(db, (workflow.GECIKTI,))

    # --- bildirimler --------------------------------------------------------

    @app.get("/bildirimler")
    def bildirimler(k: Kullanici = Depends(mevcut_kullanici), db: Session = Depends(get_db)):
        q = select(Bildirim).where(Bildirim.kullanici_id == k.id).order_by(
            Bildirim.id.desc()).limit(100)
        return [{"id": b.id, "talep_id": b.talep_id, "icerik": b.icerik,
                 "okundu": b.okundu, "zaman": b.zaman} for b in db.scalars(q)]

    @app.post("/bildirimler/{bildirim_id}/okundu")
    def okundu(bildirim_id: int, k: Kullanici = Depends(mevcut_kullanici),
               db: Session = Depends(get_db)):
        b = db.get(Bildirim, bildirim_id)
        if b is None or b.kullanici_id != k.id:
            raise workflow.Bulunamadi()
        b.okundu = True
        return {"tamam": True}

    # --- yönetim ------------------------------------------------------------

    @app.post("/admin/ice-aktar")
    def ice_aktar(dosya: UploadFile = File(...),
                  k: Kullanici = Depends(rol_gerekli("sistem_yoneticisi")),
                  db: Session = Depends(get_db)):
        rapor = importer.ice_aktar(db, dosya.file)
        if "hata" in rapor:
            raise HTTPException(422, rapor["hata"])
        workflow.denetle(db, k.id, "ice_aktar", "", {
            "ogrenci_yeni": rapor["ogrenci_yeni"], "veli_yeni": rapor["veli_yeni"]})
        return rapor

    @app.post("/talepler/toplu-karar")
    def toplu_karar(veri: TopluKararIstegi, k: Kullanici = Depends(rol_gerekli("yonetici")),
                    db: Session = Depends(get_db)):
        sonuc = {"islenen": 0, "atlanan": []}
        for tid in veri.idler:
            t = db.get(IzinTalebi, tid)
            try:
                if t is None:
                    raise workflow.Bulunamadi("Talep bulunamadı")
                workflow.yonetici_karar(db, k, t, onay=veri.onay, aciklama=veri.aciklama,
                                        now=zaman.simdi())
                sonuc["islenen"] += 1
            except workflow.IsKuraliHatasi as e:
                sonuc["atlanan"].append({"id": tid, "neden": e.mesaj})
        return sonuc

    # --- ayarlar ve öğrenci listesi -----------------------------------------

    @app.get("/ayarlar")
    def ayarlari_getir(_: Kullanici = Depends(mevcut_kullanici), db: Session = Depends(get_db)):
        return {**ayarlar.hepsi(db), "gunler": list(ayarlar.GUNLER)}

    @app.put("/ayarlar")
    def ayarlari_guncelle(veri: dict, k: Kullanici = Depends(rol_gerekli("yonetici")),
                          db: Session = Depends(get_db)):
        try:
            yeni = ayarlar.guncelle(db, veri)
        except ayarlar.AyarHatasi as e:
            raise HTTPException(422, str(e))
        workflow.denetle(db, k.id, "ayar_guncelle", "", veri)
        return {**yeni, "gunler": list(ayarlar.GUNLER)}

    @app.get("/ogrenciler")
    def ogrenciler(q: str = "", k: Kullanici = Depends(
            rol_gerekli("yonetici", "belletmen", "sistem_yoneticisi")),
            db: Session = Depends(get_db)):
        sorgu = select(Ogrenci).order_by(Ogrenci.ad_soyad)
        if q.strip():
            desen = f"%{q.strip()}%"
            sorgu = sorgu.where(Ogrenci.ad_soyad.ilike(desen) | Ogrenci.okul_no.ilike(desen))
        return [{"id": o.id, "okul_no": o.okul_no, "ad_soyad": o.ad_soyad,
                 "sinif": o.sinif, "oda": o.oda} for o in db.scalars(sorgu.limit(50))]

    @app.get("/ogrenciler/{ogrenci_id}/evci-hakki")
    def evci_hakki(ogrenci_id: int, k: Kullanici = Depends(mevcut_kullanici),
                   db: Session = Depends(get_db)):
        if k.rol == "veli" and not workflow.veli_mi(db, k, ogrenci_id):
            raise workflow.Yasak()
        if k.rol == "ogrenci":
            ogr = db.get(Ogrenci, ogrenci_id)
            if ogr is None or ogr.kullanici_id != k.id:
                raise workflow.Yasak()
        if k.rol == "sistem_yoneticisi":
            raise workflow.Yasak()
        simdi = zaman.simdi()
        return {"kullanilan": workflow.evci_sayisi(db, ogrenci_id, simdi.year, simdi.month),
                "hak": ayarlar.al(db, "aylik_evci_hakki")}

    # --- hesap yönetimi -----------------------------------------------------

    @app.get("/admin/kullanicilar")
    def kullanicilar(rol: str | None = None, q: str = "",
                     _: Kullanici = Depends(rol_gerekli("sistem_yoneticisi")),
                     db: Session = Depends(get_db)):
        sorgu = select(Kullanici).order_by(Kullanici.rol, Kullanici.ad_soyad)
        if rol:
            sorgu = sorgu.where(Kullanici.rol == rol)
        if q.strip():
            desen = f"%{q.strip()}%"
            sorgu = sorgu.where(Kullanici.ad_soyad.ilike(desen)
                                | Kullanici.kullanici_adi.ilike(desen))
        return [{**kullanici_dict(u), "aktif": u.aktif,
                 "kayit_bekliyor": u.kayit_kodu_hash is not None}
                for u in db.scalars(sorgu.limit(200))]

    @app.get("/admin/sablon")
    def sablon(_: Kullanici = Depends(rol_gerekli("sistem_yoneticisi"))):
        return Response(importer.sablon_xlsx(), headers={
            "Content-Disposition": 'attachment; filename="ogrenci-veli-sablon.xlsx"'},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.post("/admin/personel", status_code=201)
    def personel_ekle(veri: PersonelIstegi,
                      k: Kullanici = Depends(rol_gerekli("sistem_yoneticisi")),
                      db: Session = Depends(get_db)):
        if veri.rol not in ("belletmen", "yonetici", "sistem_yoneticisi"):
            raise HTTPException(422, "Rol belletmen, yonetici veya sistem_yoneticisi olmalı")
        if db.scalars(select(Kullanici).where(
                Kullanici.kullanici_adi == veri.kullanici_adi)).first():
            raise HTTPException(409, "Bu kullanıcı adı zaten var")
        kod = kayit_kodu_uret()
        u = Kullanici(kullanici_adi=veri.kullanici_adi, ad_soyad=veri.ad_soyad, rol=veri.rol,
                      eposta=veri.eposta, aktif=False, kayit_kodu_hash=kod_hashle(kod))
        db.add(u)
        db.flush()
        workflow.denetle(db, k.id, "personel_ekle", f"kullanici:{u.id}", {"rol": veri.rol})
        return {**kullanici_dict(u), "kod": kod}

    @app.post("/admin/kullanicilar/{kullanici_id}/kod-yenile")
    def kod_yenile(kullanici_id: int, k: Kullanici = Depends(rol_gerekli("sistem_yoneticisi")),
                   db: Session = Depends(get_db)):
        u = db.get(Kullanici, kullanici_id)
        if u is None:
            raise workflow.Bulunamadi()
        kod = kayit_kodu_uret()
        u.kayit_kodu_hash = kod_hashle(kod)
        u.sifre_hash = None  # eski şifre geçersiz, kod ile yeniden belirlenir
        u.aktif = False
        workflow.denetle(db, k.id, "kod_yenile", f"kullanici:{u.id}")
        return {**kullanici_dict(u), "kod": kod}

    @app.post("/admin/kullanicilar/{kullanici_id}/pasif")
    def pasif_yap(kullanici_id: int, k: Kullanici = Depends(rol_gerekli("sistem_yoneticisi")),
                  db: Session = Depends(get_db)):
        u = db.get(Kullanici, kullanici_id)
        if u is None:
            raise workflow.Bulunamadi()
        if u.id == k.id:
            raise HTTPException(409, "Kendi hesabınızı pasifleştiremezsiniz")
        u.aktif = False
        workflow.denetle(db, k.id, "pasif", f"kullanici:{u.id}")
        return {"tamam": True}

    @app.get("/saglik")
    def saglik():
        return {"durum": "ok"}

    # --- arayüz (statik) ----------------------------------------------------
    static = Path(__file__).parent / "static"

    @app.middleware("http")
    async def guvenlik_basliklari(request: Request, call_next):
        yanit = await call_next(request)
        yanit.headers.setdefault("X-Content-Type-Options", "nosniff")
        yanit.headers.setdefault("Referrer-Policy", "same-origin")
        yanit.headers.setdefault("X-Frame-Options", "DENY")
        yanit.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        if yanit.headers.get("content-type", "").startswith("application/json"):
            yanit.headers["Cache-Control"] = "no-store"
        return yanit

    @app.get("/", include_in_schema=False)
    def anasayfa():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js", include_in_schema=False)
    def servis_calisani():
        return FileResponse(static / "sw.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(static / "manifest.webmanifest",
                            media_type="application/manifest+json")

    @app.get("/bos-form", include_in_schema=False)
    def bos_form():
        return FileResponse(static / "bos-form.html")

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app

