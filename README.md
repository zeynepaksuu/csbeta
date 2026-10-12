# Agent Flow

Firma bazlı yapay zeka asistanı platformu. Her firma için ayrı bilgi bankası ve
system prompt tanımlanır; sohbet mesajları arka planda işlenip sonuçlar canlı
olarak arayüze akar.

## Neler yapılabilir

- **Firma yönetimi:** Firma profili, bilgi bankası (ürün, hizmet, fiyat, SSS) ve
  firmaya özel davranış kuralları (system prompt) tanımlama.
- **Sohbet:** Seçilen firmanın bilgisiyle beslenen agent üzerinden oturum bazlı
  sohbet; geçmiş oturumları saklama ve silme.
- **Asenkron çalışma:** Mesajlar bir iş kuyruğuna alınır, worker tarafından
  işlenir; uzun süren işler arayüzü bloklamaz.
- **Canlı güncelleme:** İş durumu ve yanıtlar WebSocket üzerinden anlık yayınlanır.
- **Harici araç entegrasyonu:** Agent, isteğe bağlı olarak harici bir araç
  sunucusuna (MCP) bağlanarak ek yeteneklerle çalışabilir. Tanımlanmazsa agent
  bu bağlantı olmadan çalışır.

## Teknolojiler

- Django 5
- PostgreSQL
- Procrastinate (iş kuyruğu / worker)
- Centrifugo (gerçek zamanlı mesajlaşma)
- Claude Agent SDK

## Kurulum

Ortam değişkenlerini hazırlayın:

```bash
cp .env.example .env
# .env içindeki token ve ayarları doldur (proje taslağı halinde suan)
```

Docker ile çalıştırın:

```bash
docker compose up --build
```

Uygulama `http://localhost:8080` adresinde çalışır.

## Geliştirme (Docker'sız)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8080
```

Ayrı bir terminalde worker'ı başlatın:

```bash
python manage.py procrastinate worker --queues agents
```

> Not: Yerel çalıştırmada PostgreSQL ve Centrifugo'nun erişilebilir olması gerekir.

## Ortam değişkenleri

Tüm ayarlar `.env` üzerinden okunur; örnek için `.env.example` dosyasına bakın.
Gizli anahtarlar koda gömülü değildir ve `.env` dosyası sürüm takibine dahil
edilmez.
