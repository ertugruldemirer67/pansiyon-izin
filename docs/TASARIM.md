# Pansiyon İzin Sistemi: MVP Tasarım Belgesi

Durum: Taslak · Kapsam: Lise pansiyonu evci / izin / mazeret yönetimi

## 1. Amaç
Kâğıtla yürüyen evci ve izin sürecini dijitale taşımak: talep, veli onayı, yönetici onayı, çıkış/giriş kaydı ve raporlama. SMS kullanılmaz. Sistem internette çalışır.

## 2. Kapsam
**MVP içinde**
- Öğrenci/veli/personel listesini Excel'den içe aktarma
- İzin talebi oluşturma (veli veya öğrenci)
- Veli onayı (veli paneli + e-posta + web push)
- Yönetici onayı/reddi (tekli ve toplu)
- QR ile çıkış/giriş okutma (belletmen)
- "Şu an dışarıdakiler" ve "geç kalanlar" listesi
- Denetim kaydı

**MVP dışında (sonra)**
- Evci hakkı hesabı ve otomatik kurallar (Aşama 2)
- Aylık/dönemlik raporlar, istatistikler (Aşama 2)
- e-Okul entegrasyonu, nöbet programı entegrasyonu (Aşama 3)

## 3. Roller ve yetkiler
| Rol | Yapabildikleri |
|---|---|
| Veli | Kendi çocuğu için talep açar/onaylar/reddeder, geçmişi görür |
| Öğrenci | Talep açar (veli onayına gider), QR kodunu gösterir, durumunu görür |
| Belletmen | Çıkış/giriş okutur, dışarıdakiler listesini görür, not ekler |
| Yönetici | Talepleri onaylar/reddeder, kural ve takvimi yönetir, raporları görür, manuel onay girer |
| Sistem yöneticisi | Kullanıcı ve içe aktarma yönetimi |

## 4. Talep akışı (durum makinesi)
```
taslak ──> veli_bekliyor ──> yonetici_bekliyor ──> onaylandi ──> disarida ──> dondu
              │                    │                  │            │
              └──> reddedildi      └──> reddedildi    └──> iptal   └──> gecikti ──> dondu
```
- Veli açtıysa `veli_bekliyor` atlanır.
- Öğrenci açtıysa veli 48 saat içinde yanıt vermezse talep `zaman_asimi` olur, yönetici isterse manuel onay verir.
- Acil izin: yönetici doğrudan `onaylandi` oluşturabilir, gerekçe zorunlu.
- `disarida` → `dondu` geçişi giriş okutmasıyla olur. Planlanan dönüş saatini aşan kayıt `gecikti` işaretlenir.

## 5. Veri modeli
```
kullanici(id, kullanici_adi[veli=telefon, ogrenci=okul_no], ad_soyad, rol, eposta, sifre_hash, kayit_kodu_hash, aktif)
ogrenci(id, kullanici_id?, okul_no, sinif, oda, qr_token)
veli_ogrenci(veli_id, ogrenci_id, yakinlik)
izin_talebi(id, ogrenci_id, acan_id, tur, cikis_zamani, donus_zamani,
            gidecegi_yer, gerekce, durum, olusturma_zamani)
onay_adimi(id, talep_id, adim[veli|yonetici], karar, karar_veren_id,
           not, zaman, yontem[panel|manuel])
hareket(id, talep_id, tip[cikis|giris], zaman, belletmen_id, not)
bildirim(id, kullanici_id, kanal[eposta|push|panel], icerik, okundu, zaman)
denetim(id, kullanici_id, islem, nesne, detay_json, zaman)
-- Aşama 2: kural(id, ad, parametre_json), evci_hakki(ogrenci_id, donem, kullanilan, hak)
```
`tur` değerleri: `evci`, `mazeret`, `saglik`, `ozel`.

## 6. Ekranlar
**Veli:** talep listesi · yeni talep · onay bekleyenler · talep detayı
**Öğrenci:** durumum · yeni talep · QR kodum
**Belletmen:** okutma ekranı (kamera + manuel arama) · dışarıdakiler · geç kalanlar
**Yönetici:** onay bekleyenler (toplu işlem) · tüm talepler/filtre · öğrenci geçmişi · manuel onay · kullanıcı/içe aktarma
Hepsi mobil öncelikli (PWA).

## 7. API (özet, REST)
```
POST /auth/giris, /auth/cikis, /auth/ilk-kayit
GET  /talepler?durum=&ogrenci=      POST /talepler
POST /talepler/{id}/veli-karar      POST /talepler/{id}/yonetici-karar
POST /talepler/{id}/iptal
POST /hareket/okut   {qr_token}   # tip otomatik: dışarıdaysa giriş, onaylı izin varsa çıkış
GET  /disaridakiler   GET /gecikenler
POST /admin/ice-aktar (xlsx)
```

## 8. Bildirimler (SMS yok)
- Panel içi bildirim (her zaman)
- E-posta: yeni talep, karar, geç kalma
- Web push: PWA kurulu cihazlara
- Geç kalma: planlanan dönüş + tolerans (varsayılan 30 dk) aşılınca veliye ve yöneticiye

## 9. Güvenlik ve KVKK
- Veli ilk kaydı okulun verdiği tek kullanımlık kodla yapılır.
- Şifreler argon2/bcrypt ile saklanır, oturumlar süreli.
- Rol bazlı erişim: veli yalnızca kendi çocuğunu görür.
- QR token rastgele ve yenilenebilir, kişisel veri taşımaz.
- Her karar ve manuel işlem denetim kaydına yazılır.
- Aydınlatma metni ve veli açık rızası ilk girişte onaylatılır.
- Günlük veritabanı yedeği; HTTPS zorunlu.

## 10. Teknoloji önerisi
- Sunucu: Python + FastAPI (alternatif: Django)
- Veritabanı: PostgreSQL (küçük okulda SQLite ile başlanabilir, ORM ile geçiş kolay)
- Arayüz: Mobil uyumlu PWA
- E-posta: SMTP (ücretsiz servis)
- Dağıtım: Docker + tek VPS
- Test: pytest, durum makinesi ve yetki testleri öncelikli

## 11. Ölçek
| | Küçük (~60) | Orta (~200) | Büyük (500+) |
|---|---|---|---|
| Veritabanı | SQLite/PostgreSQL | PostgreSQL | PostgreSQL |
| Okutma | Tek nokta | Tek/çift | Çoklu nokta |
| Onay | Tekli | Toplu önerilir | Toplu zorunlu |

## 12. Açık sorular
1. Kâğıt izin formundaki alanlar nelerdir? (örnek form isteniyor)
2. Evci günleri/saatleri ve hak sayısı nedir?
3. Tolerans süresi ve geç kalma yaptırımı var mı?
4. Aynı öğrencinin birden fazla velisi varsa kimin onayı yeterli?
5. Belletmenler kendi telefonuyla mı okutacak?

## 13. İş planı
1. Depo, iskelet, kimlik doğrulama ve roller
2. Excel içe aktarma
3. Talep akışı ve durum makinesi (+ testler)
4. Veli paneli ve bildirimler
5. QR okutma ve dışarıdakiler listesi
6. Yönetici ekranları, denetim kaydı
7. Pilot kullanım ve geri bildirim
