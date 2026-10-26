# Pansiyon İzin Sistemi

Lise pansiyonu için evci / izin / mazeret yönetimi: talep, veli onayı, yönetici onayı, QR ile çıkış–giriş kaydı, geç kalma takibi. SMS kullanılmaz; bildirimler panel içindedir (e-posta ve web push sonraki aşama).

Tasarım: [docs/TASARIM.md](docs/TASARIM.md)

## Çalıştırma

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY="uzun-rastgele-bir-deger"   # üretimde zorunlu
export DATABASE_URL="sqlite:///./pansiyon.db"  # PostgreSQL: postgresql+psycopg://...

# ilk yönetici hesabı
python -m app.cli kullanici-ekle --kullanici-adi admin --ad-soyad "Sistem Yöneticisi" --rol sistem_yoneticisi

uvicorn --factory app.main:create_app
```

API dokümantasyonu: `http://localhost:8000/docs`

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
