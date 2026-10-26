"use strict";
/* Yazdırılabilir izin formu. t = talep (boş form için null). */
function formuOlustur(t, okulAdi) {
  const dolu = (v) => (t ? v : "");
  const kutu = (etiket, secili) => h("span", { class: "kutu" }, secili ? "☒" : "☐", " " + etiket);
  const alan = (etiket, deger, genis) =>
    h("div", { class: "alan" + (genis ? " genis" : "") },
      h("span", { class: "etiket" }, etiket), h("span", { class: "deger" }, deger || ""));
  const imza = (baslik, alt) =>
    h("div", { class: "imza" }, h("div", { class: "imza-baslik" }, baslik),
      h("div", { class: "imza-alan" }), h("div", { class: "imza-alt" }, alt || ""));

  const onay = (adim) => (t ? t.onaylar.find((o) => o.adim === adim) : null);
  const veliOnay = onay("veli"), yonOnay = onay("yonetici");
  const cikis = t && t.hareketler.find((x) => x.tip === "cikis");
  const giris = t && t.hareketler.find((x) => x.tip === "giris");
  const veli = t && t.veliler && t.veliler[0];

  return h("section", { class: "form-sayfa" },
    h("header", { class: "form-baslik" },
      h("div", { class: "okul" }, okulAdi ? okulAdi : "………………………………………… Pansiyonu"),
      h("h1", null, "PANSİYON ÇIKIŞ İZİN FORMU"),
      t ? h("div", { class: "no" }, "Form No: " + t.id) : h("div", { class: "no" }, "Form No: ………")),

    h("h2", null, "1. Öğrenci Bilgileri"),
    h("div", { class: "izgara" },
      alan("Adı Soyadı", dolu(t && t.ogrenci.ad_soyad), true),
      alan("Sınıfı", dolu(t && t.ogrenci.sinif)),
      alan("Okul No", dolu(t && t.ogrenci.okul_no)),
      alan("Oda No", dolu(t && t.ogrenci.oda))),

    h("h2", null, "2. İzin Bilgileri"),
    h("div", { class: "turler" }, h("span", { class: "etiket" }, "İzin Türü:"),
      ...Object.entries(TURLER).map(([k, ad]) => kutu(ad, t && t.tur === k))),
    h("div", { class: "izgara" },
      alan("Çıkış Tarihi / Saati", t ? zamanYaz(t.cikis_zamani) : "……/……/………… ……:……"),
      alan("Dönüş Tarihi / Saati", t ? zamanYaz(t.donus_zamani) : "……/……/………… ……:……"),
      alan("Gideceği Yer / Adres", dolu(t && t.gidecegi_yer), true),
      alan("İzin Gerekçesi", dolu(t && t.gerekce), true)),

    h("h2", null, "3. Veli Bilgileri ve Onayı"),
    h("div", { class: "izgara" },
      alan("Veli Adı Soyadı", dolu(veli && veli.ad_soyad)),
      alan("Yakınlık", dolu(veli && veli.yakinlik)),
      alan("Telefon", dolu(veli && veli.telefon)),
      alan("Onay", veliOnay
        ? (veliOnay.karar === "onay" ? "Onaylandı" : "Reddedildi") +
          " (" + zamanYaz(veliOnay.zaman) + (veliOnay.yontem === "manuel" ? ", telefonla" : "") + ")"
        : "")),
    h("p", { class: "metin" },
      "Yukarıda bilgileri yazılı öğrencimin belirtilen tarih ve saatler arasında pansiyondan " +
      "çıkmasına izin veriyorum. Dönüş saatine kadar öğrencinin sorumluluğunu üstleniyorum."),
    h("div", { class: "imzalar" }, imza("Veli İmzası", "Tarih: ……/……/…………")),

    h("h2", null, "4. Yönetim Onayı"),
    h("div", { class: "turler" },
      kutu("Uygundur", yonOnay && yonOnay.karar === "onay"),
      kutu("Uygun Değildir", yonOnay && yonOnay.karar === "red"),
      h("span", { class: "etiket" }, "Açıklama:"), h("span", { class: "deger" },
        yonOnay ? yonOnay.aciklama + (yonOnay.yontem === "acil" ? " (acil izin)" : "") : "")),
    h("div", { class: "imzalar" }, imza("Pansiyon Müdür Yardımcısı", "Tarih: ……/……/…………")),

    h("h2", null, "5. Çıkış ve Dönüş Kaydı (Nöbetçi Belletmen)"),
    h("div", { class: "izgara" },
      alan("Çıkış Saati", cikis ? zamanYaz(cikis.zaman) : ""),
      alan("Dönüş Saati", giris ? zamanYaz(giris.zaman) : ""),
      alan("Geç Dönüş", giris ? (giris.aciklama ? "Evet" : "Hayır") : "")),
    h("div", { class: "imzalar iki" }, imza("Çıkışı Yapan Belletmen"), imza("Girişi Yapan Belletmen")),

    h("footer", { class: "form-alt" },
      "Bu form çıkış öncesinde doldurulup onaylanmalı; öğrenci dönüşte belletmene teslim edilmelidir."));
}
