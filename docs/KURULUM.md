# Ücretsiz bulutta kurulum (telefondan yapılabilir)

Toplam süre yaklaşık 15 dakika. İki ücretsiz hesap gerekir: **Neon** (veritabanı, kalıcı) ve **Render** (uygulama). Kredi kartı istemezler.

> **Önce okuyun – kişisel veri:** Bu sistem reşit olmayan öğrencilerin ve velilerin kişisel verisini tutar. Ücretsiz bulut hizmetleri yurt dışındadır (aşağıda sunucu bölgesini Frankfurt seçiyoruz). Gerçek öğrenci verisi girmeden önce okul müdürlüğünün onayını alın, velilere aydınlatma metni verin ve gerekirse İl/İlçe Milli Eğitim Müdürlüğü bilgi işlemine danışın. Önce **deneme verisiyle** (uydurma isimler) deneyin.

## 1. Veritabanı: Neon
1. https://neon.tech adresine girin, **Google veya GitHub ile kaydolun**.
2. **Create project** → ad: `pansiyon-izin` → **Region: Europe (Frankfurt)** → Postgres 16 → Create.
3. Açılan ekranda **Connection string** kutusunu bulun, **Show password** deyip tamamını kopyalayın.
   `postgresql://kullanici:parola@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require` biçimindedir. Bunu bir yere not edin; 3. adımda lazım.

## 2. Uygulama: Render
1. https://render.com adresine girin, **GitHub ile kaydolun** (depoya erişim izni isteyecek; yalnızca `pansiyon-izin` deposunu seçin).
2. **New +** → **Blueprint** → `pansiyon-izin` deposunu seçin → Render `render.yaml` dosyasını okur.
3. Sizden üç değer ister:
   - `DATABASE_URL`: Neon'dan kopyaladığınız adres
   - `ILK_YONETICI_ADI`: örn. `admin`
   - `ILK_YONETICI_SIFRE`: güçlü bir şifre (en az 8 karakter)
4. **Apply / Deploy** deyin. 3-5 dakika içinde yeşil "Live" görünür.
5. Render size `https://pansiyon-izin-xxxx.onrender.com` gibi bir adres verir. Bu sizin sistem adresinizdir (HTTPS hazır; kamera ve "Ana ekrana ekle" çalışır).

## 3. İlk giriş ve düzenleme
1. Adrese girin, kullanıcı adı/şifre olarak 2. adımda yazdıklarınızla giriş yapın (sistem yöneticisi).
2. Render panelinde **Environment** bölümünden `ILK_YONETICI_SIFRE` değişkenini **silin** (artık gerekmez).
3. **Personel** sekmesinden yönetici (müdür yardımcısı) ve belletmen hesaplarını açın; çıkan kayıt kodlarını kişilere iletin.
4. **İçe aktar** sekmesinden Excel şablonunu indirip öğrenci/veli listesini yükleyin; kayıt kodlarını yazdırıp dağıtın.
5. Yönetici hesabıyla **Ayarlar**'dan evci günlerini, saatlerini ve aylık hakkı girin.

## 4. Uygulamanın uyumaması için (önerilir)
Render'ın ücretsiz planı 15 dakika kullanılmazsa uygulamayı uyutur; ilk açılış ~1 dakika sürer. Bunu önlemek için:
1. https://uptimerobot.com → ücretsiz hesap → **Add New Monitor**
2. Tür: HTTP(s), URL: `https://<adresiniz>/saglik`, aralık: 5 dakika.

## 5. Telefona uygulama olarak ekleme
- Android Chrome: ⋮ menü → **Ana ekrana ekle / Uygulamayı yükle**
- iPhone Safari: Paylaş → **Ana Ekrana Ekle**

## Bilinen sınırlar (ücretsiz plan)
- Render ücretsiz planı çok kullanıcılı yoğun anlarda yavaşlayabilir; yüzlerce öğrenci için ücretli plana geçmek gerekebilir.
- Neon ücretsiz planında depolama 0,5 GB'tır; bu sistem için yıllarca yeter.
- **Yedek:** Neon, ücretsiz planda kısa süreli geri alma sunar; uzun vadeli yedek için dönemde bir kez Neon panelinden dışa aktarım almanız önerilir.
- Şifre unutulursa sistem yöneticisi **Hesaplar → Kod yenile** ile yeni kayıt kodu üretir.
