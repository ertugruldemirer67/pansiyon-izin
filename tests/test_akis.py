from datetime import timedelta

from tests.conftest import SIMDI

CIKIS = SIMDI + timedelta(hours=2)
DONUS = SIMDI + timedelta(days=2)


def talep_govdesi(ogrenci_id, **ek):
    govde = {"ogrenci_id": ogrenci_id, "tur": "evci", "cikis_zamani": CIKIS.isoformat(),
             "donus_zamani": DONUS.isoformat(), "gidecegi_yer": "Ankara", "gerekce": "Hafta sonu"}
    govde.update(ek)
    return govde


def test_ogrenci_talebi_tam_akis(istemci, veri, saat):
    ogr, veli, yon, bel = (istemci("1001"), istemci("veli1"),
                           istemci("yonetici1"), istemci("belletmen1"))
    oid = veri["ogrenci"].id

    r = ogr.post("/talepler", json=talep_govdesi(oid))
    assert r.status_code == 201
    tid = r.json()["id"]
    assert r.json()["durum"] == "veli_bekliyor"

    # veliye bildirim gitti
    assert any("onayınız" in b["icerik"] for b in veli.get("/bildirimler").json())

    r = veli.post(f"/talepler/{tid}/veli-karar", json={"onay": True})
    assert r.json()["durum"] == "yonetici_bekliyor"

    r = yon.post(f"/talepler/{tid}/yonetici-karar", json={"onay": True})
    assert r.json()["durum"] == "onaylandi"

    # çıkış saatinden önce okutma: pencere dışı
    r = bel.post("/hareket/okut", json={"qr_token": "qr-ali"})
    assert r.status_code == 409

    saat.t = CIKIS
    r = bel.post("/hareket/okut", json={"qr_token": "qr-ali"})
    assert r.json()["tip"] == "cikis"
    assert [d["id"] for d in bel.get("/disaridakiler").json()] == [tid]

    saat.t = DONUS - timedelta(hours=1)
    r = bel.post("/hareket/okut", json={"qr_token": "qr-ali"})
    assert r.json() == {"tip": "giris", "gec": False, "ogrenci": "Ali Veli", "talep_id": tid}
    assert bel.get("/disaridakiler").json() == []
    assert ogr.get(f"/talepler/{tid}").json()["durum"] == "dondu"


def test_veli_acarsa_veli_adimi_atlanir(istemci, veri):
    r = istemci("veli1").post("/talepler", json=talep_govdesi(veri["ogrenci"].id))
    assert r.json()["durum"] == "yonetici_bekliyor"
    assert r.json()["onaylar"][0]["adim"] == "veli"


def test_baska_veli_goremez_ve_acamaz(istemci, veri):
    r = istemci("veli1").post("/talepler", json=talep_govdesi(veri["ogrenci"].id))
    tid = r.json()["id"]
    diger = istemci("veli2")
    assert diger.get(f"/talepler/{tid}").status_code == 403
    assert diger.get("/talepler").json() == []
    assert diger.post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).status_code == 403
    assert istemci("1002").post("/talepler",
                                json=talep_govdesi(veri["ogrenci"].id)).status_code == 403


def test_veli_olmayan_veli_karari_veremez(istemci, veri):
    tid = istemci("1001").post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    assert istemci("veli2").post(f"/talepler/{tid}/veli-karar",
                                 json={"onay": True}).status_code == 403
    assert istemci("belletmen1").post(f"/talepler/{tid}/veli-karar",
                                      json={"onay": True}).status_code == 403


def test_yonetici_manuel_veli_onayi_aciklama_ister(istemci, veri):
    tid = istemci("1001").post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    yon = istemci("yonetici1")
    assert yon.post(f"/talepler/{tid}/veli-karar", json={"onay": True}).status_code == 422
    r = yon.post(f"/talepler/{tid}/veli-karar",
                 json={"onay": True, "aciklama": "Telefonla onay alındı"})
    assert r.json()["durum"] == "yonetici_bekliyor"
    assert r.json()["onaylar"][0]["yontem"] == "manuel"


def test_yonetici_red_gerekce_ister(istemci, veri):
    tid = istemci("veli1").post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    yon = istemci("yonetici1")
    assert yon.post(f"/talepler/{tid}/yonetici-karar", json={"onay": False}).status_code == 422
    r = yon.post(f"/talepler/{tid}/yonetici-karar", json={"onay": False, "aciklama": "Sınav haftası"})
    assert r.json()["durum"] == "reddedildi"


def test_acil_izin(istemci, veri):
    yon = istemci("yonetici1")
    govde = talep_govdesi(veri["ogrenci"].id, tur="saglik", gerekce="")
    assert yon.post("/talepler", json=govde).status_code == 422
    govde["gerekce"] = "Hastaneye sevk"
    r = yon.post("/talepler", json=govde)
    assert r.status_code == 201 and r.json()["durum"] == "onaylandi"
    assert r.json()["onaylar"][0]["yontem"] == "acil"


def test_cakisan_talep_reddedilir(istemci, veri):
    c = istemci("veli1")
    assert c.post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).status_code == 201
    assert c.post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).status_code == 409


def test_gecersiz_zaman_ve_tur(istemci, veri):
    c = istemci("veli1")
    oid = veri["ogrenci"].id
    assert c.post("/talepler", json=talep_govdesi(oid, tur="tatil")).status_code == 422
    ters = talep_govdesi(oid, cikis_zamani=DONUS.isoformat(), donus_zamani=CIKIS.isoformat())
    assert c.post("/talepler", json=ters).status_code == 422
    gecmis = talep_govdesi(oid, cikis_zamani=(SIMDI - timedelta(days=3)).isoformat(),
                           donus_zamani=(SIMDI - timedelta(days=1)).isoformat())
    assert c.post("/talepler", json=gecmis).status_code == 422


def test_gec_donus_ve_gecikenler(istemci, veri, saat):
    veli, yon, bel = istemci("veli1"), istemci("yonetici1"), istemci("belletmen1")
    tid = veli.post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    yon.post(f"/talepler/{tid}/yonetici-karar", json={"onay": True})
    saat.t = CIKIS
    bel.post("/hareket/okut", json={"qr_token": "qr-ali"})

    saat.t = DONUS + timedelta(minutes=10)  # tolerans içinde
    assert bel.get("/gecikenler").json() == []

    saat.t = DONUS + timedelta(hours=2)
    gecikenler = bel.get("/gecikenler").json()
    assert [t["id"] for t in gecikenler] == [tid] and gecikenler[0]["durum"] == "gecikti"
    assert any("geçti" in b["icerik"] for b in veli.get("/bildirimler").json())

    r = bel.post("/hareket/okut", json={"qr_token": "qr-ali"})
    assert r.json()["tip"] == "giris" and r.json()["gec"] is True


def test_veli_zaman_asimi(istemci, veri, saat):
    tid = istemci("1001").post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    saat.t = SIMDI + timedelta(hours=49)
    istemci("belletmen1").get("/disaridakiler")  # tarama tetikler
    assert istemci("1001").get(f"/talepler/{tid}").json()["durum"] == "zaman_asimi"


def test_iptal(istemci, veri):
    tid = istemci("veli1").post("/talepler", json=talep_govdesi(veri["ogrenci"].id)).json()["id"]
    assert istemci("veli2").post(f"/talepler/{tid}/iptal").status_code == 403
    assert istemci("veli1").post(f"/talepler/{tid}/iptal").json()["durum"] == "iptal"
    assert istemci("veli1").post(f"/talepler/{tid}/iptal").status_code == 409


def test_okutma_yetkisi(istemci, veri):
    assert istemci("veli1").post("/hareket/okut", json={"qr_token": "qr-ali"}).status_code == 403
    assert istemci("belletmen1").post("/hareket/okut", json={"qr_token": "yok"}).status_code == 404
    assert istemci("belletmen1").post("/hareket/okut",
                                      json={"qr_token": "qr-ali"}).status_code == 409
