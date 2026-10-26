# Pansiyon İzin Sistemi

Lise pansiyonu için evci / izin / mazeret yönetimi: talep, veli onayı, yönetici onayı, QR ile çıkış–giriş kaydı, geç kalma takibi. SMS kullanılmaz; bildirimler panel içindedir (e-posta ve web push sonraki aşama).

## Arayüz
Aynı adres hem **sade web sitesi** (kurulum gerektirmez) hem **telefona eklenebilir uygulama (PWA)** olarak çalışır:
- Tarayıcıdan adrese girin → kullanılabilir.
- Telefonda: Chrome ⋮ → "Ana ekrana ekle" / Safari Paylaş → "Ana Ekrana Ekle" → uygulama gibi açılır.
- Roller: veli, öğrenci (QR kodum), belletmen (kamera ile QR okutma + numara ile kayıt), yönetici (toplu onay, acil izin, kurallar), sistem yöneticisi (Excel içe aktarma, hesaplar, kayıt kodları).
- **Kamera ve PWA kurulumu için HTTPS şarttır** (localhost hariç).
- **İzin formu:** her talepte "Formu yazdır" ile A4 form oluşur; boş form `/bos-form` adresinde ve `docs/bos-izin-formu.pdf` dosyasındadır.

Tasarım: [docs/TASARIM.md](docs/TASARIM.md)

## Yayına alma
Ücretsiz bulutta (Neon + Render) telefondan kurulum: [docs/KURULUM.md](docs/KURULUM.md)

## Çalıştırma

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY="uzun-rastgele-bir-deger"   # üretimde zorunlu
export COOKIE_SECURE=1                         # HTTPS arkasında zorunlu
export DATABASE_URL="sqlite:///./pansiyon.db"  # PostgreSQL: postgresql://... (otomatik düzeltilir)

# ilk yönetici hesabı
python -m app.cli kullanici-ekle --kullanici-adi admin --ad-soyad "Sistem Yöneticisi" --rol sistem_yoneticisi

uvicorn --factory app.main:create_app
```

API dokümantasyonu: `http://localhost:8000/docs`

## Kurallar (yönetici panelinden değiştirilir)
**Ayarlar** sayfasından, kodlamaya gerek kalmadan: evci günleri/saatleri (birden fazla aralık), aylık evci hakkı, tolerans, veli yanıt süresi, okul adı. Yeni kural yalnızca sonradan açılan taleplere uygulanır; yönetici acil izni kuralları aşar.

## Kullanıma alma adımları
1. `sistem_yoneticisi` ile giriş yapın, Excel listesini `POST /admin/ice-aktar` ile yükleyin.
   Sütunlar: `okul_no, ogrenci_ad_soyad, veli_ad_soyad, veli_telefon` (+ isteğe bağlı `sinif, oda, yakinlik`).
2. Yanıtta dönen **tek kullanımlık kayıt kodlarını** veli/öğrencilere iletin (kodlar bir daha gösterilmez).
3. Veli/öğrenci `POST /auth/ilk-kayit` ile şifresini belirler.
4. Belletmen ve yönetici hesaplarını CLI ile ekleyin.

## Testler
```bash
python -m pytest
```

## Ayarlar (ortam değişkenleri)
| Değişken | Varsayılan | Anlamı |
|---|---|---|
| `SECRET_KEY` | rastgele (her başlatmada değişir) | Oturum imzası |
| `TOLERANS_DAKIKA` | 30 | Çıkış öncesi / dönüş sonrası tolerans |
| `VELI_ZAMAN_ASIMI_SAAT` | 48 | Yanıtsız veli onayı zaman aşımı |
| `OTURUM_SAAT` | 12 | Oturum süresi |
| `COOKIE_SECURE` | 0 | HTTPS arkasında 1 yapın |
| `SAAT_DILIMI` | Europe/Istanbul | Sunucunun "şimdi" saati |
| `ILK_YONETICI_ADI` / `ILK_YONETICI_SIFRE` | yok | Kabuk erişimi olmayan ortamda ilk sistem yöneticisini açar (yalnızca hiç yoksa) |
| `TEST_DATABASE_URL` | yok | Verilirse testler bu PostgreSQL'e karşı koşar (tabloları siler!) |

`TOLERANS_DAKIKA` ve `VELI_ZAMAN_ASIMI_SAAT` yalnızca ilk varsayılandır; panelden değiştirilen değer önceliklidir.
