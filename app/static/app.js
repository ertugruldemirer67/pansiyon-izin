"use strict";

const S = { ben: null, ayar: null, kodlar: null, temizlik: [], sayac: null };

const DURUM_AD = {
  veli_bekliyor: "Veli onayı bekliyor", yonetici_bekliyor: "Yönetici onayı bekliyor",
  onaylandi: "Onaylandı", disarida: "Dışarıda", gecikti: "Geç kaldı", dondu: "Döndü",
  reddedildi: "Reddedildi", iptal: "İptal edildi", zaman_asimi: "Zaman aşımı",
  kullanilmadi: "Kullanılmadı",
};
const DURUM_SINIF = {
  veli_bekliyor: "bekle", yonetici_bekliyor: "bekle", onaylandi: "iyi", disarida: "bilgi",
  gecikti: "kotu", dondu: "nötr", reddedildi: "kotu", iptal: "nötr", zaman_asimi: "nötr",
  kullanilmadi: "nötr",
};
const ROL_AD = { veli: "Veli", ogrenci: "Öğrenci", belletmen: "Belletmen", yonetici: "Yönetici",
  sistem_yoneticisi: "Sistem yöneticisi" };

// ---------------------------------------------------------------- yardımcılar

function hataMetni(v) {
  if (!v) return "";
  const d = v.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e.msg).join("; ");
  return "";
}

async function api(yol, { method = "GET", body, form } = {}) {
  const o = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
  if (form) o.body = form;
  let r;
  try { r = await fetch(yol, o); } catch { throw new Error("Sunucuya ulaşılamıyor. İnternet bağlantınızı kontrol edin."); }
  let veri = null;
  try { veri = await r.json(); } catch { /* gövde yok */ }
  if (r.status === 401 && !yol.startsWith("/auth/")) {
    S.ben = null; location.hash = "#/giris";
    throw new Error("Oturum süresi doldu, tekrar giriş yapın.");
  }
  if (!r.ok) throw new Error(hataMetni(veri) || "İşlem başarısız (" + r.status + ")");
  return veri;
}

function toast(mesaj, tip) {
  const el = h("div", { class: "toast " + (tip || "") , role: "status" }, mesaj);
  document.body.append(el);
  setTimeout(() => el.remove(), tip === "hata" ? 6000 : 3000);
}

async function dene(islem) {
  try { return await islem(); } catch (e) { toast(e.message, "hata"); return undefined; }
}

function soru({ baslik, etiket, zorunlu, onay = "Tamam", metin }) {
  return new Promise((coz) => {
    const alan = h("textarea", { rows: "3", placeholder: etiket || "" });
    const dlg = h("dialog", { class: "kutu-dialog" });
    const bitir = (v) => { dlg.close(); dlg.remove(); coz(v); };
    const tamam = h("button", { class: "birincil", onclick: () => {
      if (zorunlu && !alan.value.trim()) { alan.focus(); return; }
      bitir(alan.value.trim());
    } }, onay);
    dlg.append(h("h3", null, baslik), metin ? h("p", null, metin) : null,
      etiket ? alan : null,
      h("div", { class: "eylemler" }, h("button", { onclick: () => bitir(null) }, "Vazgeç"), tamam));
    document.body.append(dlg);
    dlg.addEventListener("cancel", () => bitir(null));
    dlg.showModal();
    if (etiket) alan.focus();
  });
}

function bilgiKutusu(baslik, satirlar) {
  const dlg = h("dialog", { class: "kutu-dialog" },
    h("h3", null, baslik), ...satirlar,
    h("div", { class: "eylemler" }, h("button", { class: "birincil", onclick: () => { dlg.close(); dlg.remove(); } }, "Kapat")));
  document.body.append(dlg);
  dlg.showModal();
}

function alanEtiket(etiket, girdi, ipucu) {
  return h("label", { class: "alan-grup" }, h("span", null, etiket), girdi, ipucu ? h("small", null, ipucu) : null);
}

function yerelInput(deger) {
  const d = deger || new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function yenileZamanlayici(fn, sn) {
  const id = setInterval(fn, sn * 1000);
  S.temizlik.push(() => clearInterval(id));
}

// ---------------------------------------------------------------- talep kartı

function talepKarti(t, { yenile, secim } = {}) {
  const rol = S.ben.rol;
  const eylemler = [];
  const calistir = (fn, mesaj) => async () => {
    const sonuc = await dene(fn);
    if (sonuc !== undefined) { toast(mesaj, "iyi"); yenile && yenile(); }
  };
  const karar = (adim, onay) => async () => {
    let aciklama = "";
    if (!onay || (adim === "veli" && rol === "yonetici")) {
      const yanit = await soru({
        baslik: onay ? "Veli adına onay" : "Reddet",
        etiket: onay ? "Açıklama (ör. Veli ile telefonda görüşüldü)" : "Red gerekçesi",
        zorunlu: rol === "yonetici" && (adim === "yonetici" || onay),
        onay: onay ? "Onayla" : "Reddet",
      });
      if (yanit === null) return;
      aciklama = yanit;
    }
    const sonuc = await dene(() => api(`/talepler/${t.id}/${adim}-karar`, { method: "POST", body: { onay, aciklama } }));
    if (sonuc !== undefined) { toast(onay ? "Onaylandı" : "Reddedildi", "iyi"); yenile && yenile(); }
  };

  if (rol === "veli" && t.durum === "veli_bekliyor") {
    eylemler.push(h("button", { class: "birincil", onclick: karar("veli", true) }, "Onayla"),
      h("button", { class: "tehlike", onclick: karar("veli", false) }, "Reddet"));
  }
  if (rol === "yonetici" && t.durum === "yonetici_bekliyor") {
    eylemler.push(h("button", { class: "birincil", onclick: karar("yonetici", true) }, "Onayla"),
      h("button", { class: "tehlike", onclick: karar("yonetici", false) }, "Reddet"));
  }
  if (rol === "yonetici" && t.durum === "veli_bekliyor") {
    eylemler.push(h("button", { onclick: karar("veli", true) }, "Veli adına onayla"));
  }
  const iptalEdebilir = ["veli_bekliyor", "yonetici_bekliyor", "onaylandi"].includes(t.durum) &&
    (rol === "veli" || rol === "yonetici" || t.acan_id === S.ben.id);
  if (iptalEdebilir) {
    eylemler.push(h("button", { onclick: async () => {
      if (!confirm("Bu talebi iptal etmek istiyor musunuz?")) return;
      calistir(() => api(`/talepler/${t.id}/iptal`, { method: "POST" }), "İptal edildi")();
    } }, "İptal et"));
  }
  eylemler.push(h("a", { class: "dugme", href: `#/form/${t.id}` }, "Formu yazdır"));

  const ayrinti = h("div", { class: "ayrinti", hidden: true },
    t.gidecegi_yer ? h("p", null, h("b", null, "Gideceği yer: "), t.gidecegi_yer) : null,
    t.gerekce ? h("p", null, h("b", null, "Gerekçe: "), t.gerekce) : null,
    ...t.onaylar.map((o) => h("p", { class: "iz" },
      `${o.adim === "veli" ? "Veli" : "Yönetici"} ${o.karar === "onay" ? "onayladı" : "reddetti"}` +
      ` (${zamanYaz(o.zaman)}${o.yontem !== "panel" ? ", " + o.yontem : ""})` +
      (o.aciklama ? ": " + o.aciklama : ""))),
    ...t.hareketler.map((x) => h("p", { class: "iz" },
      `${x.tip === "cikis" ? "Çıkış" : "Giriş"}: ${zamanYaz(x.zaman)}${x.aciklama ? " (" + x.aciklama + ")" : ""}`)),
    t.veliler && t.veliler.length ? h("p", null, h("b", null, "Veli: "),
      t.veliler.map((v) => `${v.ad_soyad} (${v.telefon})`).join(", ")) : null);

  const baslik = h("div", { class: "kart-ust" },
    secim ? secim : null,
    h("div", { class: "kart-ad" },
      h("strong", null, t.ogrenci.ad_soyad),
      h("small", null, [t.ogrenci.sinif, t.ogrenci.oda && "Oda " + t.ogrenci.oda].filter(Boolean).join(" · "))),
    h("span", { class: "rozet " + DURUM_SINIF[t.durum] }, DURUM_AD[t.durum] || t.durum));

  return h("article", { class: "kart" }, baslik,
    h("p", { class: "zaman" }, h("b", null, TURLER[t.tur] || t.tur), " · ",
      zamanYaz(t.cikis_zamani), " → ", zamanYaz(t.donus_zamani)),
    ayrinti,
    h("div", { class: "eylemler" },
      h("button", { class: "yazi", onclick: (e) => { ayrinti.hidden = !ayrinti.hidden;
        e.target.textContent = ayrinti.hidden ? "Ayrıntı" : "Gizle"; } }, "Ayrıntı"),
      ...eylemler));
}

function bos(mesaj) { return h("p", { class: "bos" }, mesaj); }

async function talepListesi(sorgu, bosMesaj) {
  const kap = h("div", { class: "liste" });
  async function yukle() {
    const liste = await api("/talepler" + (sorgu || ""));
    kap.replaceChildren(...(liste.length ? liste.map((t) => talepKarti(t, { yenile: yukle })) : [bos(bosMesaj)]));
  }
  await yukle();
  return kap;
}

// ---------------------------------------------------------------- giriş

function gorunumGiris() {
  const hata = h("p", { class: "hata", hidden: true });
  const kullanici = h("input", { name: "kullanici_adi", autocomplete: "username", required: true,
    placeholder: "Telefon (veli) / okul no (öğrenci) / kullanıcı adı", inputmode: "text" });
  const sifre = h("input", { type: "password", autocomplete: "current-password", required: true });
  const kod = h("input", { autocomplete: "off", placeholder: "Okuldan aldığınız kayıt kodu", autocapitalize: "characters" });
  const yeniSifre = h("input", { type: "password", autocomplete: "new-password", minlength: "8",
    placeholder: "En az 8 karakter" });
  let ilkKayit = false;

  const kayitAlanlari = h("div", { hidden: true },
    alanEtiket("Kayıt kodu", kod), alanEtiket("Yeni şifre", yeniSifre));
  const girisAlani = alanEtiket("Şifre", sifre);
  const dugme = h("button", { class: "birincil buyuk", type: "submit" }, "Giriş yap");
  const gecis = h("button", { type: "button", class: "yazi" }, "İlk kez giriyorum (kayıt kodum var)");

  gecis.addEventListener("click", () => {
    ilkKayit = !ilkKayit;
    kayitAlanlari.hidden = !ilkKayit; girisAlani.hidden = ilkKayit;
    sifre.required = !ilkKayit;
    dugme.textContent = ilkKayit ? "Şifremi belirle" : "Giriş yap";
    gecis.textContent = ilkKayit ? "Zaten şifrem var" : "İlk kez giriyorum (kayıt kodum var)";
  });

  const form = h("form", { class: "giris-formu", onsubmit: async (e) => {
    e.preventDefault(); hata.hidden = true; dugme.disabled = true;
    try {
      if (ilkKayit) {
        await api("/auth/ilk-kayit", { method: "POST", body: {
          kullanici_adi: kullanici.value.trim(), kod: kod.value.trim(), sifre: yeniSifre.value } });
        await api("/auth/giris", { method: "POST", body: { kullanici_adi: kullanici.value.trim(), sifre: yeniSifre.value } });
      } else {
        await api("/auth/giris", { method: "POST", body: { kullanici_adi: kullanici.value.trim(), sifre: sifre.value } });
      }
      await oturumuYukle();
      location.hash = varsayilanRota();
    } catch (err) { hata.textContent = err.message; hata.hidden = false; }
    finally { dugme.disabled = false; }
  } },
    alanEtiket("Kullanıcı adı", kullanici), girisAlani, kayitAlanlari, hata, dugme, gecis);

  return h("div", { class: "giris" },
    h("img", { src: "/static/icons/icon-192.png", alt: "", width: "72", height: "72" }),
    h("h1", null, "Pansiyon İzin Sistemi"), form,
    h("p", { class: "ipucu" }, "Şifrenizi unuttuysanız pansiyon yönetiminden yeni kayıt kodu isteyin."),
    h("p", { class: "ipucu" }, h("a", { href: "/bos-form", target: "_blank", rel: "noopener" }, "Boş izin formunu yazdır")));
}

// ---------------------------------------------------------------- yeni talep

async function gorunumYeni({ acil } = {}) {
  const rol = S.ben.rol;
  S.ayar = await api("/ayarlar"); // kurallar yönetici tarafından değişmiş olabilir
  const hata = h("p", { class: "hata", hidden: true });
  let ogrenciSecici;
  let seciliOgrenci = () => null;

  if (rol === "veli") {
    const cocuklar = S.ben.cocuklar || [];
    ogrenciSecici = h("select", { required: true }, ...cocuklar.map((c) => h("option", { value: c.id }, `${c.ad_soyad} (${c.sinif})`)));
    seciliOgrenci = () => Number(ogrenciSecici.value);
  } else if (rol === "ogrenci") {
    ogrenciSecici = h("input", { value: S.ben.ad_soyad, disabled: true });
    seciliOgrenci = () => S.ben.ogrenci.id;
  } else {
    const ara = h("input", { type: "search", placeholder: "Öğrenci adı veya okul no" });
    const secim = h("select", { required: true, size: "4" });
    let zaman;
    const getir = async () => {
      const liste = await api("/ogrenciler?q=" + encodeURIComponent(ara.value));
      secim.replaceChildren(...liste.map((o) => h("option", { value: o.id }, `${o.ad_soyad} · ${o.sinif} · No ${o.okul_no}`)));
    };
    ara.addEventListener("input", () => { clearTimeout(zaman); zaman = setTimeout(() => dene(getir), 250); });
    await getir();
    ogrenciSecici = h("div", null, ara, secim);
    seciliOgrenci = () => Number(secim.value);
  }

  const tur = h("select", null, ...Object.entries(TURLER).map(([k, ad]) => h("option", { value: k }, ad)));
  const baslangic = new Date(); baslangic.setHours(baslangic.getHours() + 1, 0, 0, 0);
  const bitis = new Date(baslangic); bitis.setDate(bitis.getDate() + 2);
  const cikis = h("input", { type: "datetime-local", required: true, value: yerelInput(baslangic) });
  const donus = h("input", { type: "datetime-local", required: true, value: yerelInput(bitis) });
  const yer = h("input", { maxlength: "256", placeholder: "Şehir / adres" });
  const gerekce = h("textarea", { rows: "3", required: !!acil, placeholder: acil ? "Zorunlu: acil izin gerekçesi" : "İsteğe bağlı" });
  const bilgi = h("p", { class: "ipucu" });

  const kuralMetni = () => {
    const a = S.ayar; const parcalar = [];
    if (a.evci_pencereleri.length) {
      parcalar.push("Evci aralıkları: " + a.evci_pencereleri.map((p) =>
        `${GUNLER[p.cikis_gun]} ${p.cikis_saat} – ${GUNLER[p.donus_gun]} ${p.donus_saat}`).join("; "));
    }
    return parcalar.join(" ");
  };
  const hakGuncelle = async () => {
    bilgi.textContent = tur.value === "evci" ? kuralMetni() : "";
    if (tur.value === "evci" && S.ayar.aylik_evci_hakki && seciliOgrenci() && rol !== "sistem_yoneticisi") {
      try {
        const r = await api(`/ogrenciler/${seciliOgrenci()}/evci-hakki`);
        bilgi.textContent += ` Bu ay evci hakkı: ${r.kullanilan}/${r.hak} kullanıldı.`;
      } catch { /* bilgi amaçlı */ }
    }
  };
  tur.addEventListener("change", hakGuncelle);
  if (ogrenciSecici.addEventListener) ogrenciSecici.addEventListener("change", hakGuncelle);
  hakGuncelle();

  const gonder = h("button", { class: "birincil buyuk", type: "submit" }, acil ? "Acil izni ver" : "Talebi gönder");
  const form = h("form", { onsubmit: async (e) => {
    e.preventDefault(); hata.hidden = true; gonder.disabled = true;
    try {
      const t = await api("/talepler", { method: "POST", body: {
        ogrenci_id: seciliOgrenci(), tur: tur.value, cikis_zamani: cikis.value, donus_zamani: donus.value,
        gidecegi_yer: yer.value, gerekce: gerekce.value } });
      toast(t.durum === "veli_bekliyor" ? "Talep velinin onayına gönderildi"
        : t.durum === "onaylandi" ? "Acil izin verildi" : "Talep yönetici onayına gönderildi", "iyi");
      location.hash = rol === "yonetici" ? "#/tum" : "#/talepler";
    } catch (err) { hata.textContent = err.message; hata.hidden = false; window.scrollTo(0, 0); }
    finally { gonder.disabled = false; }
  } },
    alanEtiket("Öğrenci", ogrenciSecici), alanEtiket("İzin türü", tur), bilgi,
    h("div", { class: "iki-sutun" }, alanEtiket("Çıkış", cikis), alanEtiket("Dönüş", donus)),
    alanEtiket("Gideceği yer", yer), alanEtiket("Gerekçe", gerekce), hata, gonder);

  return h("div", null, h("h2", null, acil ? "Acil izin" : "Yeni izin talebi"),
    acil ? h("p", { class: "ipucu" }, "Acil izin doğrudan onaylanır; evci kuralları uygulanmaz. İşlem kayda geçer.") : null,
    form);
}

// ---------------------------------------------------------------- öğrenci QR, bildirimler

function gorunumQr() {
  const o = S.ben.ogrenci;
  const qr = qrcode(0, "M");
  qr.addData(o.qr_token); qr.make();
  return h("div", { class: "qr-kap" }, h("h2", null, "QR kodum"),
    h("img", { class: "qr", alt: "QR kod", src: qr.createDataURL(8, 4) }),
    h("p", null, S.ben.ad_soyad), h("p", { class: "ipucu" },
      "Çıkış ve girişte belletmene gösterin. Kodu başkasıyla paylaşmayın."));
}

async function gorunumBildirimler() {
  const liste = await api("/bildirimler");
  const kap = h("div", { class: "liste" }, ...(liste.length ? liste.map((b) =>
    h("button", { class: "bildirim " + (b.okundu ? "" : "yeni"), onclick: async (e) => {
      if (!b.okundu) { await dene(() => api(`/bildirimler/${b.id}/okundu`, { method: "POST" })); sayaciYenile(); }
      e.currentTarget.classList.remove("yeni");
      if (b.talep_id) location.hash = "#/talep/" + b.talep_id;
    } }, h("span", null, b.icerik), h("small", null, zamanYaz(b.zaman)))) : [bos("Bildirim yok")]));
  return h("div", null, h("h2", null, "Bildirimler"), kap);
}

async function gorunumTekTalep(id) {
  const t = await api("/talepler/" + id);
  const kap = h("div", null);
  const goster = async () => { kap.replaceChildren(talepKarti(await api("/talepler/" + id), { yenile: goster })); };
  kap.append(talepKarti(t, { yenile: goster }));
  return h("div", null, h("h2", null, "Talep #" + id), kap);
}

// ---------------------------------------------------------------- belletmen

async function gorunumOkut() {
  const sonuc = h("div", { class: "okut-sonuc", hidden: true, "aria-live": "polite" });
  const video = h("video", { playsinline: true, muted: true, class: "kamera", hidden: true });
  const kameraDurum = h("p", { class: "ipucu" });
  let sonKod = "", sonZaman = 0;

  const goster = (sinif, baslik, alt) => {
    sonuc.className = "okut-sonuc " + sinif; sonuc.hidden = false;
    sonuc.replaceChildren(h("strong", null, baslik), alt ? h("span", null, alt) : null);
    if (navigator.vibrate) navigator.vibrate(sinif === "kotu" ? [200, 100, 200] : 80);
  };
  const okut = async (govde) => {
    try {
      const r = await api("/hareket/okut", { method: "POST", body: govde });
      if (r.tip === "cikis") goster("iyi", `ÇIKIŞ: ${r.ogrenci}`, "Çıkış kaydedildi");
      else goster(r.gec ? "uyari" : "bilgi", `GİRİŞ: ${r.ogrenci}`, r.gec ? "GEÇ DÖNÜŞ kaydedildi" : "Dönüş kaydedildi");
      listeyiYenile();
    } catch (e) { goster("kotu", "İŞLEM YAPILAMADI", e.message); }
  };

  const numara = h("input", { inputmode: "numeric", placeholder: "Okul numarası", autocomplete: "off" });
  const elleForm = h("form", { class: "satir", onsubmit: (e) => { e.preventDefault();
    if (numara.value.trim()) { okut({ okul_no: numara.value.trim() }); numara.value = ""; } } },
    numara, h("button", { class: "birincil", type: "submit" }, "Kaydet"));

  const kameraDugme = h("button", { class: "birincil buyuk", type: "button", onclick: async () => {
    kameraDugme.disabled = true;
    try {
      const durdur = await kameraBaslat(video, async (kod) => {
        const simdi = Date.now();
        if (kod === sonKod && simdi - sonZaman < 6000) return;
        sonKod = kod; sonZaman = simdi;
        await okut({ qr_token: kod });
      });
      S.temizlik.push(durdur);
      video.hidden = false; kameraDugme.hidden = true;
    } catch (e) {
      kameraDugme.disabled = false;
      kameraDurum.textContent = "Kamera açılamadı (" + (e.message || e.name) + "). Kamera için HTTPS gerekir; okul numarasıyla da kaydedebilirsiniz.";
    }
  } }, "Kamerayı aç ve QR okut");

  const liste = h("div", { class: "liste" });
  const listeyiYenile = async () => {
    try {
      const l = await api("/disaridakiler");
      liste.replaceChildren(h("h3", null, `Şu an dışarıda: ${l.length}`),
        ...(l.length ? l.map((t) => h("div", { class: "satir-kart" },
          h("div", null, h("strong", null, t.ogrenci.ad_soyad), h("small", null, ` ${t.ogrenci.sinif}`)),
          h("span", { class: "rozet " + DURUM_SINIF[t.durum] },
            t.durum === "gecikti" ? "GEÇ · " + zamanYaz(t.donus_zamani) : "Dönüş " + zamanYaz(t.donus_zamani)))) : [bos("Dışarıda öğrenci yok")]));
    } catch { /* oturum süresi dolmuş olabilir */ }
  };
  await listeyiYenile();
  yenileZamanlayici(listeyiYenile, 30);

  return h("div", null, h("h2", null, "Çıkış / Giriş"), kameraDugme, video, kameraDurum,
    sonuc, h("h3", null, "Numara ile kaydet"), elleForm, liste);
}

async function kameraBaslat(video, kodBulunca) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error("tarayıcı desteklemiyor");
  const akim = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  video.srcObject = akim; await video.play();
  const detektor = "BarcodeDetector" in window ? new BarcodeDetector({ formats: ["qr_code"] }) : null;
  const tuval = document.createElement("canvas");
  const ctx = tuval.getContext("2d", { willReadFrequently: true });
  let calisiyor = true;
  const dongu = async () => {
    if (!calisiyor) return;
    if (video.readyState >= 2) {
      try {
        let kod = null;
        if (detektor) { const r = await detektor.detect(video); if (r.length) kod = r[0].rawValue; }
        else if (typeof jsQR === "function") {
          tuval.width = video.videoWidth; tuval.height = video.videoHeight;
          ctx.drawImage(video, 0, 0);
          const d = ctx.getImageData(0, 0, tuval.width, tuval.height);
          const r = jsQR(d.data, d.width, d.height, { inversionAttempts: "dontInvert" });
          if (r) kod = r.data;
        }
        if (kod) await kodBulunca(kod);
      } catch { /* kare atla */ }
    }
    if (calisiyor) setTimeout(dongu, 300);
  };
  dongu();
  return () => { calisiyor = false; akim.getTracks().forEach((t) => t.stop()); };
}

async function gorunumDisarida() {
  const kap = h("div", { class: "liste" });
  const yukle = async () => {
    const l = await api("/disaridakiler");
    kap.replaceChildren(h("p", { class: "ipucu" }, `${l.length} öğrenci dışarıda, ${l.filter((t) => t.durum === "gecikti").length} geç kalan.`),
      ...(l.length ? l.map((t) => talepKarti(t, { yenile: yukle })) : [bos("Dışarıda öğrenci yok")]));
  };
  await yukle(); yenileZamanlayici(() => dene(yukle), 30);
  return h("div", null, h("h2", null, "Dışarıdakiler"), kap);
}

// ---------------------------------------------------------------- yönetici

async function gorunumBekleyen() {
  const kap = h("div", { class: "liste" });
  const yukle = async () => {
    const [yon, veli] = await Promise.all([
      api("/talepler?durum=yonetici_bekliyor"), api("/talepler?durum=veli_bekliyor")]);
    const secilen = new Set();
    const topluDugme = h("button", { class: "birincil", disabled: true, onclick: async () => {
      const r = await dene(() => api("/talepler/toplu-karar", { method: "POST", body: { idler: [...secilen], onay: true } }));
      if (r) { toast(`${r.islenen} talep onaylandı` + (r.atlanan.length ? `, ${r.atlanan.length} atlandı` : ""), "iyi"); yukle(); }
    } }, "Seçilenleri onayla");
    const kutu = (t) => h("input", { type: "checkbox", "aria-label": t.ogrenci.ad_soyad, onchange: (e) => {
      e.target.checked ? secilen.add(t.id) : secilen.delete(t.id);
      topluDugme.disabled = !secilen.size; topluDugme.textContent = secilen.size ? `Seçilenleri onayla (${secilen.size})` : "Seçilenleri onayla";
    } });
    kap.replaceChildren(
      h("h3", null, `Onayınızı bekleyen (${yon.length})`),
      yon.length ? topluDugme : null,
      ...(yon.length ? yon.map((t) => talepKarti(t, { yenile: yukle, secim: kutu(t) })) : [bos("Onay bekleyen talep yok")]),
      veli.length ? h("h3", null, `Veli yanıtı bekleyen (${veli.length})`) : null,
      ...veli.map((t) => talepKarti(t, { yenile: yukle })));
  };
  await yukle();
  yenileZamanlayici(() => dene(yukle), 60);
  return h("div", null, h("h2", null, "Bekleyen talepler"), kap);
}

async function gorunumTum() {
  const durum = h("select", null, h("option", { value: "" }, "Tüm durumlar"),
    ...Object.entries(DURUM_AD).map(([k, ad]) => h("option", { value: k }, ad)));
  const alan = h("div");
  const yukle = async () => {
    alan.replaceChildren(await talepListesi(durum.value ? "?durum=" + durum.value : "", "Kayıt yok"));
  };
  durum.addEventListener("change", () => dene(yukle));
  await yukle();
  return h("div", null, h("h2", null, "Tüm talepler"), alanEtiket("Durum", durum), alan);
}

async function gorunumAyarlar() {
  const a = await api("/ayarlar");
  const pencereler = structuredClone(a.evci_pencereleri);
  const okul = h("input", { value: a.okul_adi, maxlength: "80" });
  const hak = h("input", { type: "number", min: "0", max: "31", value: a.aylik_evci_hakki });
  const tolerans = h("input", { type: "number", min: "0", max: "240", value: a.tolerans_dakika });
  const zamanAsimi = h("input", { type: "number", min: "1", max: "720", value: a.veli_zaman_asimi_saat });
  const liste = h("div", { class: "pencereler" });

  const gunSec = (deger, degis) => {
    const s = h("select", { "aria-label": "Gün" }, ...GUNLER.map((g, i) => h("option", { value: i }, g)));
    s.value = deger; s.addEventListener("change", () => degis(Number(s.value))); return s;
  };
  const saatGir = (deger, degis) => {
    const i = h("input", { type: "time", value: deger, required: true });
    i.addEventListener("change", () => degis(i.value)); return i;
  };
  const ciz = () => liste.replaceChildren(...(pencereler.length ? pencereler.map((p, i) =>
    h("div", { class: "pencere" },
      h("div", null, h("small", null, "Çıkış"), gunSec(p.cikis_gun, (v) => (p.cikis_gun = v)), saatGir(p.cikis_saat, (v) => (p.cikis_saat = v))),
      h("div", null, h("small", null, "Dönüş"), gunSec(p.donus_gun, (v) => (p.donus_gun = v)), saatGir(p.donus_saat, (v) => (p.donus_saat = v))),
      h("button", { type: "button", class: "tehlike", "aria-label": "Aralığı sil", onclick: () => { pencereler.splice(i, 1); ciz(); } }, "Sil")))
    : [h("p", { class: "ipucu" }, "Aralık tanımlı değil: evci talepleri herhangi bir zamana açılabilir.")]));
  ciz();

  const kaydet = h("button", { class: "birincil buyuk", type: "submit" }, "Kaydet");
  const form = h("form", { onsubmit: async (e) => {
    e.preventDefault(); kaydet.disabled = true;
    const r = await dene(() => api("/ayarlar", { method: "PUT", body: {
      okul_adi: okul.value, aylik_evci_hakki: Number(hak.value), tolerans_dakika: Number(tolerans.value),
      veli_zaman_asimi_saat: Number(zamanAsimi.value), evci_pencereleri: pencereler } }));
    kaydet.disabled = false;
    if (r) { S.ayar = r; toast("Ayarlar kaydedildi", "iyi"); }
  } },
    h("h3", null, "Evci günleri ve saatleri"),
    h("p", { class: "ipucu" }, "Evci talebinin çıkış ve dönüşü bu aralıklardan birinin içinde olmalı. Acil izinler bu kuraldan muaftır. Yeni kural yalnızca bundan sonra açılan taleplere uygulanır."),
    liste,
    h("div", { class: "satir" },
      h("button", { type: "button", onclick: () => { pencereler.push({ cikis_gun: 4, cikis_saat: "17:00", donus_gun: 6, donus_saat: "20:00" }); ciz(); } }, "+ Aralık ekle (Cuma 17:00 – Pazar 20:00)")),
    h("h3", null, "Diğer kurallar"),
    alanEtiket("Aylık evci hakkı", hak, "0 = sınırsız. Reddedilen/iptal edilen talepler hakkı düşürmez."),
    alanEtiket("Tolerans (dakika)", tolerans, "Çıkış öncesi okutma payı ve geç kalma payı."),
    alanEtiket("Veli yanıt süresi (saat)", zamanAsimi, "Süre dolunca öğrenci talebi zaman aşımına uğrar."),
    alanEtiket("Okul / pansiyon adı", okul, "İzin formunun başlığında görünür."),
    kaydet);
  return h("div", null, h("h2", null, "Ayarlar"), form);
}

// ---------------------------------------------------------------- sistem yöneticisi

function kodGoster(u) {
  S.kodlar = [{ ad_soyad: u.ad_soyad, kullanici_adi: u.kullanici_adi, rol: u.rol, kod: u.kod }];
  bilgiKutusu("Kayıt kodu oluşturuldu", [
    h("p", null, `${u.ad_soyad} (${u.kullanici_adi})`),
    h("p", { class: "kod-buyuk" }, u.kod),
    h("p", { class: "ipucu" }, "Bu kod bir daha gösterilmez. İlk girişte 'İlk kez giriyorum' seçilerek kullanılır."),
    h("a", { class: "dugme", href: "#/kodlar" }, "Yazdırılabilir kağıt")]);
}

async function gorunumHesaplar() {
  const ara = h("input", { type: "search", placeholder: "Ad veya kullanıcı adı" });
  const rol = h("select", null, h("option", { value: "" }, "Tüm roller"),
    ...Object.entries(ROL_AD).map(([k, ad]) => h("option", { value: k }, ad)));
  const liste = h("div", { class: "liste" });
  const yukle = async () => {
    const l = await api(`/admin/kullanicilar?q=${encodeURIComponent(ara.value)}&rol=${rol.value}`);
    liste.replaceChildren(...(l.length ? l.map((u) => h("div", { class: "satir-kart" },
      h("div", null, h("strong", null, u.ad_soyad), h("small", null, ` ${ROL_AD[u.rol]} · ${u.kullanici_adi}`)),
      h("div", { class: "eylemler" },
        h("span", { class: "rozet " + (!u.aktif ? "nötr" : "iyi") }, u.kayit_bekliyor ? "Kayıt bekliyor" : u.aktif ? "Aktif" : "Pasif"),
        h("button", { onclick: async () => {
          if (!confirm(`${u.ad_soyad} için yeni kayıt kodu üretilsin mi? Mevcut şifre geçersiz olur.`)) return;
          const r = await dene(() => api(`/admin/kullanicilar/${u.id}/kod-yenile`, { method: "POST" }));
          if (r) { kodGoster(r); yukle(); }
        } }, "Kod yenile"),
        u.aktif ? h("button", { class: "tehlike", onclick: async () => {
          if (!confirm(`${u.ad_soyad} hesabı pasifleştirilsin mi?`)) return;
          if (await dene(() => api(`/admin/kullanicilar/${u.id}/pasif`, { method: "POST" }))) yukle();
        } }, "Pasifleştir") : null))) : [bos("Kayıt yok")]));
  };
  let zaman;
  ara.addEventListener("input", () => { clearTimeout(zaman); zaman = setTimeout(() => dene(yukle), 250); });
  rol.addEventListener("change", () => dene(yukle));
  await yukle();
  return h("div", null, h("h2", null, "Hesaplar"), h("div", { class: "satir" }, ara, rol), liste);
}

function gorunumIceAktar() {
  const dosya = h("input", { type: "file", accept: ".xlsx", required: true });
  const sonuc = h("div");
  const gonder = h("button", { class: "birincil buyuk", type: "submit" }, "Yükle");
  const form = h("form", { onsubmit: async (e) => {
    e.preventDefault(); gonder.disabled = true;
    const fd = new FormData(); fd.append("dosya", dosya.files[0]);
    const r = await dene(() => api("/admin/ice-aktar", { method: "POST", form: fd }));
    gonder.disabled = false;
    if (!r) return;
    S.kodlar = r.kodlar;
    sonuc.replaceChildren(
      h("p", { class: "iyi-kutu" }, `${r.ogrenci_yeni} yeni öğrenci, ${r.ogrenci_guncel} güncellenen öğrenci, ${r.veli_yeni} yeni veli.`),
      r.hatalar.length ? h("div", { class: "hata" }, h("b", null, "Atlanan satırlar:"), h("ul", null, ...r.hatalar.map((x) => h("li", null, x)))) : null,
      r.kodlar.length ? h("a", { class: "dugme birincil", href: "#/kodlar" }, `${r.kodlar.length} kayıt kodunu yazdır`) : null,
      r.kodlar.length ? h("p", { class: "ipucu" }, "Kodlar yalnızca şimdi gösterilir; sayfadan ayrılmadan yazdırın.") : null);
  } }, alanEtiket("Excel dosyası (.xlsx)", dosya), gonder);
  return h("div", null, h("h2", null, "Öğrenci / veli listesi yükle"),
    h("p", null, "İlk satır başlık olmalı. Sütunlar: ",
      h("code", null, "okul_no, ogrenci_ad_soyad, veli_ad_soyad, veli_telefon"),
      " (isteğe bağlı: ", h("code", null, "sinif, oda, yakinlik"), "). Aynı dosya tekrar yüklenebilir; mevcut kayıtlar güncellenir."),
    h("a", { class: "dugme", href: "/admin/sablon" }, "Örnek şablonu indir"), form, sonuc);
}

function gorunumPersonel() {
  const ad = h("input", { required: true, minlength: "2" });
  const kullanici = h("input", { required: true, minlength: "3", autocapitalize: "none" });
  const rol = h("select", null, h("option", { value: "belletmen" }, "Belletmen"),
    h("option", { value: "yonetici" }, "Yönetici (müdür yardımcısı)"),
    h("option", { value: "sistem_yoneticisi" }, "Sistem yöneticisi"));
  const gonder = h("button", { class: "birincil buyuk", type: "submit" }, "Hesap oluştur");
  return h("div", null, h("h2", null, "Personel ekle"), h("form", { onsubmit: async (e) => {
    e.preventDefault(); gonder.disabled = true;
    const r = await dene(() => api("/admin/personel", { method: "POST", body: {
      ad_soyad: ad.value, kullanici_adi: kullanici.value.trim(), rol: rol.value } }));
    gonder.disabled = false;
    if (r) { kodGoster(r); ad.value = ""; kullanici.value = ""; }
  } }, alanEtiket("Ad soyad", ad), alanEtiket("Kullanıcı adı", kullanici, "Giriş için kullanılır (ör. ahmet.belletmen)"),
    alanEtiket("Rol", rol), gonder));
}

function gorunumKodlar() {
  if (!S.kodlar || !S.kodlar.length) return h("div", null, h("h2", null, "Kayıt kodları"), bos("Gösterilecek kod yok. Kodlar yalnızca oluşturulduğu anda gösterilir."));
  return h("div", null,
    h("div", { class: "arac-cubugu" }, h("button", { class: "birincil buyuk", onclick: () => window.print() }, "Yazdır"),
      h("p", { class: "ipucu" }, "Çıktıyı keserek ilgili kişilere dağıtın; sonra güvenli biçimde imha edin.")),
    h("div", { class: "kodlar" }, ...S.kodlar.map((k) => h("div", { class: "kod-kagit" },
      h("b", null, S.ayar.okul_adi + " – İzin Sistemi"),
      h("div", null, `${k.ad_soyad} (${ROL_AD[k.rol] || k.rol})`),
      h("div", null, "Kullanıcı adı: ", h("b", null, k.kullanici_adi)),
      h("div", null, "Kayıt kodu: ", h("b", { class: "kod-yazi" }, k.kod)),
      h("small", null, `${location.origin} adresinden “İlk kez giriyorum” seçeneğiyle şifrenizi belirleyin.`)))));
}

// ---------------------------------------------------------------- form yazdırma

async function gorunumForm(id) {
  const t = await api("/talepler/" + id);
  return h("div", { class: "form-onizleme" },
    h("div", { class: "arac-cubugu" },
      h("button", { onclick: () => history.back() }, "← Geri"), " ",
      h("button", { class: "birincil", onclick: () => window.print() }, "Yazdır / PDF olarak kaydet")),
    formuOlustur(t, S.ayar.okul_adi));
}

// ---------------------------------------------------------------- kabuk ve yönlendirme

const MENU = {
  veli: [["talepler", "Taleplerim"], ["yeni", "Yeni talep"], ["bildirim", "Bildirimler"]],
  ogrenci: [["talepler", "Durumum"], ["yeni", "Yeni talep"], ["qr", "QR kodum"], ["bildirim", "Bildirimler"]],
  belletmen: [["okut", "Okut"], ["disarida", "Dışarıdakiler"]],
  yonetici: [["bekleyen", "Bekleyenler"], ["tum", "Talepler"], ["acil", "Acil izin"], ["ayarlar", "Ayarlar"], ["bildirim", "Bildirimler"]],
  sistem_yoneticisi: [["hesaplar", "Hesaplar"], ["ice-aktar", "İçe aktar"], ["personel", "Personel"]],
};

function varsayilanRota() { return "#/" + MENU[S.ben.rol][0][0]; }

async function oturumuYukle() {
  S.ben = await api("/ben");
  S.ayar = await api("/ayarlar");
  await sayaciYenile();
  clearInterval(S.sayac);
  S.sayac = setInterval(sayaciYenile, 60000);
}

async function sayaciYenile() {
  const el = document.getElementById("bildirim-sayac");
  if (!S.ben || !["veli", "ogrenci", "yonetici"].includes(S.ben.rol)) return;
  try {
    const l = await api("/bildirimler");
    const n = l.filter((b) => !b.okundu).length;
    if (el) { el.textContent = n || ""; el.hidden = !n; }
    S.okunmamis = n;
  } catch { /* sessiz */ }
}

function kabuk(icerik, girisli = true) {
  const kok = document.getElementById("uygulama");
  if (!girisli) { kok.replaceChildren(h("main", { class: "icerik" }, icerik)); return; }
  const aktif = location.hash.split("/")[1];
  kok.replaceChildren(
    h("header", { class: "ust uygulama-kabugu" },
      h("div", null, h("strong", null, S.ayar.okul_adi), h("small", null, `${S.ben.ad_soyad} · ${ROL_AD[S.ben.rol]}`)),
      h("div", { class: "eylemler" },
        ["veli", "ogrenci", "yonetici"].includes(S.ben.rol) ? h("a", { class: "zil", href: "#/bildirim", "aria-label": "Bildirimler" }, "🔔",
          h("span", { id: "bildirim-sayac", class: "sayac", hidden: !S.okunmamis }, S.okunmamis || "")) : null,
        h("button", { onclick: async () => {
          await dene(() => api("/auth/cikis", { method: "POST" }));
          S.ben = null; S.kodlar = null; clearInterval(S.sayac); location.hash = "#/giris";
        } }, "Çıkış"))),
    h("main", { class: "icerik" }, icerik),
    h("nav", { class: "alt uygulama-kabugu" }, ...MENU[S.ben.rol].map(([yol, ad]) =>
      h("a", { href: "#/" + yol, class: yol === aktif ? "secili" : "" }, ad))));
}

async function yonlendir() {
  S.temizlik.splice(0).forEach((f) => { try { f(); } catch { /* yoksay */ } });
  if (!S.ben) { try { await oturumuYukle(); } catch { /* giriş gerekli */ } }
  if (!S.ben) { kabuk(gorunumGiris(), false); return; }
  const [, yol, arg] = location.hash.split("/");
  const rol = S.ben.rol;
  if (!yol || yol === "giris") { location.hash = varsayilanRota(); return; }

  const izinli = new Set(MENU[rol].map(([y]) => y));
  const ozel = { talep: ["veli", "ogrenci", "yonetici", "belletmen"], form: ["veli", "ogrenci", "yonetici", "belletmen"],
    kodlar: ["sistem_yoneticisi"] };
  if (!izinli.has(yol) && !(ozel[yol] && ozel[yol].includes(rol))) { location.hash = varsayilanRota(); return; }

  const gorunumler = {
    talepler: () => h("div", null, h("h2", null, rol === "veli" ? "Taleplerim" : "Durumum"), talepListesiYuvasi()),
    yeni: () => gorunumYeni(), acil: () => gorunumYeni({ acil: true }),
    qr: gorunumQr, bildirim: gorunumBildirimler, okut: gorunumOkut, disarida: gorunumDisarida,
    bekleyen: gorunumBekleyen, tum: gorunumTum, ayarlar: gorunumAyarlar,
    hesaplar: gorunumHesaplar, "ice-aktar": gorunumIceAktar, personel: gorunumPersonel, kodlar: gorunumKodlar,
    talep: () => gorunumTekTalep(arg), form: () => gorunumForm(arg),
  };
  const yuklenen = h("p", { class: "ipucu" }, "Yükleniyor…");
  kabuk(yuklenen);
  try {
    const icerik = await gorunumler[yol]();
    if (location.hash.split("/")[1] !== yol) return; // kullanıcı başka sayfaya geçti
    kabuk(icerik);
    if (icerik.__sonra) icerik.__sonra();
  } catch (e) { kabuk(h("p", { class: "hata" }, e.message)); }
}

function talepListesiYuvasi() {
  const yuva = h("div", null, h("p", { class: "ipucu" }, "Yükleniyor…"));
  talepListesi("", "Henüz talep yok. “Yeni talep” ile başlayabilirsiniz.").then((l) => yuva.replaceChildren(l))
    .catch((e) => yuva.replaceChildren(h("p", { class: "hata" }, e.message)));
  return yuva;
}

window.addEventListener("hashchange", yonlendir);
window.addEventListener("DOMContentLoaded", () => {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  yonlendir();
});
