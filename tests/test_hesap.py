import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.conftest import SIFRE


def excel(satirlar):
    wb = Workbook()
    ws = wb.active
    ws.append(["okul_no", "ogrenci_ad_soyad", "sinif", "oda", "veli_ad_soyad", "veli_telefon"])
    for s in satirlar:
        ws.append(s)
    cikti = io.BytesIO()
    wb.save(cikti)
    cikti.seek(0)
    return cikti


def test_giris_hatali_sifre_ve_limit(uygulama, veri):
    c = TestClient(uygulama)
    for _ in range(5):
        r = c.post("/auth/giris", json={"kullanici_adi": "veli1", "sifre": "yanlis"})
        assert r.status_code == 401
    # limit dolunca doğru şifre bile reddedilir
    r = c.post("/auth/giris", json={"kullanici_adi": "veli1", "sifre": SIFRE})
    assert r.status_code == 429


def test_oturumsuz_erisim(uygulama, veri):
    c = TestClient(uygulama)
    assert c.get("/talepler").status_code == 401
    assert c.get("/ben").status_code == 401


def test_ben_veli_cocuklari(istemci, veri):
    r = istemci("veli1").get("/ben").json()
    assert [c["ad_soyad"] for c in r["cocuklar"]] == ["Ali Veli"]
    assert "qr_token" in istemci("1001").get("/ben").json()["ogrenci"]


def test_excel_ice_aktar_ve_ilk_kayit(uygulama, veri):
    # sistem yöneticisi
    from app.models import Kullanici
    from app.security import sifre_hashle
    with uygulama.state.oturum_fabrikasi() as db:
        db.add(Kullanici(kullanici_adi="sysadmin", ad_soyad="Sys", rol="sistem_yoneticisi",
                         sifre_hash=sifre_hashle(SIFRE)))
        db.commit()
    admin = TestClient(uygulama)
    assert admin.post("/auth/giris", json={"kullanici_adi": "sysadmin", "sifre": SIFRE}).status_code == 200

    dosya = excel([
        ["2001", "Deniz Kaya", "9-A", "3", "Hale Kaya", "0532 111 22 33"],
        ["2002", "Mert Kaya", "11-B", "4", "Hale Kaya", "05321112233"],  # aynı veli, kardeş
        ["", "Eksik Satır", "", "", "", ""],
    ])
    r = admin.post("/admin/ice-aktar", files={"dosya": ("liste.xlsx", dosya)})
    assert r.status_code == 200, r.text
    rapor = r.json()
    assert rapor["ogrenci_yeni"] == 2 and rapor["veli_yeni"] == 1
    assert len(rapor["hatalar"]) == 1
    veli_kod = next(k for k in rapor["kodlar"] if k["rol"] == "veli")
    assert veli_kod["kullanici_adi"] == "5321112233"

    # tekrar içe aktarma yeni hesap/kod üretmez
    dosya.seek(0)
    ikinci = admin.post("/admin/ice-aktar", files={"dosya": ("liste.xlsx", dosya)}).json()
    assert ikinci["ogrenci_yeni"] == 0 and ikinci["kodlar"] == []

    # ilk kayıt: yanlış kod, doğru kod, kod tek kullanımlık
    veli = TestClient(uygulama)
    ilk = {"kullanici_adi": "5321112233", "sifre": "yeni-sifre-9"}
    assert veli.post("/auth/giris", json={"kullanici_adi": "5321112233",
                                          "sifre": "yeni-sifre-9"}).status_code == 401
    assert veli.post("/auth/ilk-kayit", json={**ilk, "kod": "YANLIS"}).status_code == 400
    assert veli.post("/auth/ilk-kayit", json={**ilk, "kod": veli_kod["kod"]}).status_code == 200
    assert veli.post("/auth/ilk-kayit", json={**ilk, "kod": veli_kod["kod"]}).status_code == 400
    assert veli.post("/auth/giris", json={"kullanici_adi": "5321112233",
                                          "sifre": "yeni-sifre-9"}).status_code == 200
    assert len(veli.get("/ben").json()["cocuklar"]) == 2


def test_ice_aktar_yetkisi(istemci, veri):
    r = istemci("yonetici1").post("/admin/ice-aktar", files={"dosya": ("x.xlsx", excel([]))})
    assert r.status_code == 403
