# 🏛 E-MUROJAAT
## PEDAGOGIKA FAKULTETI UCHUN PROFESSIONAL ELEKTRON MUROJAATLAR TELEGRAM BOTI

Professional, xavfsiz va to‘liq avtomatlashtirilgan elektron murojaatlar axborot tizimi. Ushbu tizim faqatgina **Telegram Bot** ichida ishlaydi — hech qanday tashqi veb dashboard yoki alohida sayt talab etilmaydi. Fakultet dekani va barcha mas'ul administratorlar o‘z vakolatlari doirasida barcha jarayonlarni Telegram bot orqali to‘liq boshqaradilar.

---

### 🌟 LOYIHANING ASOSIY XUSUSIYATLARI

1. **Yagona va mustaqil Telegram Bot**:
   - Web kabinet, dashboard yoki uchinchi tomon dasturlariga ehtiyoj yo‘q.
   - Foydalanuvchilar va dekanat o‘rtasidagi barcha operatsiyalar (qabul qilish, biriktirish, javob yuborish, statistika) 100% Telegram ichida amalga oshiriladi.
2. **Noyob Murojaat Raqamlash Tizimi**:
   - Har bir murojaatga takrorlanmas `PF-2026-000001` formatidagi raqam avtomatik biriktiriladi (`PF` — Pedagogika fakulteti, joriy yil va 6 xonali ketma-ketlik).
   - Race-condition va dublikatlardan tranzaksion darajada himoyalangan.
3. **Bosqichma-bosqich FSM Murojaat Yuborish**:
   - 7 bosqichli qat'iy nazorat: Murojaat turi ➡️ Fakultet yo‘nalishi ➡️ Mavzu ➡️ Mazmuni ➡️ Fayllar (PDF, DOCX, JPG va boshqalar) ➡️ Maxfiylik ➡️ Yakuniy tasdiqlash.
4. **Qat'iy Rolli Xavfsizlik (RBAC)**:
   - `👑 SUPER ADMINISTRATOR`: Barcha boshqaruv, xodimlar, sozlamalar, hisobotlar.
   - `🏛 DEKAN`: Barcha oddiy va maxfiy murojaatlar, xodimlarga topshiriq biriktirish, rasmiy javob berish, monitoring.
   - `⚙️ ADMINISTRATOR`: Murojaatlarni ko‘rib chiqish, biriktirish, statuslarni yangilash.
   - `👤 MAS'UL XODIM`: Faqat o‘ziga biriktirilgan murojaatlar bilan ishlash, ichki izoh qoldirish, xulosa va javob loyihasini taqdim etish.
   - `👤 MUROJAATCHI`: O‘z murojaatlarini kuzatish va dekanat bilan muloqot qilish.
5. **Maxfiy Murojaatlar Mexanizmi**:
   - Foydalanuvchi "Maxfiy murojaat"ni tanlaganda, murojaat faqat Dekan va Super Administratorga ko‘rinadi. Boshqa xodimlar unga kira olmaydi.
6. **Dekanat bilan To‘g‘ridan-to‘g‘ri Yozishmalar**:
   - Har bir murojaat bo‘yicha alohida xabarlar oqimi.
   - Ichki xizmat izohlari (`is_internal=True`) foydalanuvchiga yuborilmaydi, faqat rasmiy javoblar yetkaziladi.
7. **Haqiqiy Ma'lumotlarga Asoslangan Statistika va Excel Eksport**:
   - Kunlik, haftalik, oylik va umumiy hisobotlar.
   - To‘liq formatlangan, jadvalli va chiroyli `.xlsx` Excel hisobotini Telegram orqali bir tugma bilan yuklab olish (openpyxl asosida).
8. **Fakultet Sozlamalarini Bot Ichidan Boshqarish**:
   - Fakultet nomi, Institut nomi, Dekan F.I.Sh., aloqa raqamlari, yo‘nalishlar va standart ijro muddatlarini bevosita botdan tahrirlash.
9. **Kiberxavfsizlik va Audit**:
   - SQL Injectiondan himoyalangan SQLAlchemy 2.0 Async ORM.
   - Barcha muhim amallarni (yaratish, status o‘zgarishi, javob yuborish, sozlamalar) qayd etuvchi `AuditLog` tizimi.
   - SQLite / PostgreSQL ma'lumotlar bazasining zaxira nusxasini (Backup) bot orqali yuklab olish imkoniyati.

---

### 📁 LOYIHA TUZILMASI

```text
e-murojaat-bot/
├── bot.py                         # Asosiy ishga tushirish fayli
├── config.py                      # Pydantic-settings konfiguratsiyasi
├── requirements.txt               # Bog'liqliklar ro'yxati
├── .env.example                   # Muhit o'zgaruvchilari namunasi
├── .env                           # Maxfiy sozlamalar
├── Dockerfile                     # Docker konteyner fayli
├── docker-compose.yml             # Docker compose (PostgreSQL + Redis + Bot)
├── alembic.ini                    # Alembic migratsiya sozlamasi
│
├── handlers/                      # Telegram xabar va callback qayta ishlovchilari
│   ├── start.py                   # /start, kutib olish va umumiy bo'limlar
│   ├── registration.py            # Foydalanuvchilarni toifalar bo'yicha ro'yxatdan o'tkazish
│   ├── profile.py                 # Mening profilim va tahrirlash
│   ├── applications.py            # 7 bosqichli FSM murojaat yuborish tizimi
│   ├── my_applications.py         # Mening murojaatlarim ro'yxati va sahifalash
│   ├── tracking.py                # Murojaat raqami bo'yicha qidirish va holatini tekshirish
│   ├── correspondence.py          # Dekanat bilan ikki tomonlama yozishmalar
│   ├── admin.py                   # /admin komandasi va admin asosiy menyusi
│   ├── admin_applications.py      # Murojaatlarni ko'rish, biriktirish, javob yuborish, rad etish
│   ├── admin_staff.py             # Xodimlarni boshqarish, tayinlash va rollar
│   ├── admin_statistics.py        # Jonli statistika va Excel (.xlsx) eksport
│   └── admin_settings.py          # Kafedra sozlamalari, yo'nalishlar va backup
│
├── keyboards/                     # Tugmalar va klaviaturalar
│   ├── main.py                    # Bosh menyu (Reply Keyboard)
│   ├── user.py                    # Ro'yxatdan o'tish va profil tugmalari
│   ├── application.py             # Murojaat yuborish jarayoni inline tugmalari
│   ├── admin.py                   # Admin boshqaruv paneli va sahifalash
│   └── staff.py                   # Mas'ul xodim va murojaatlar ko'rish tugmalari
│
├── states/                        # Aiogram FSM holatlari
│   ├── registration.py            # Ro'yxatdan o'tish holatlari
│   ├── application.py             # Murojaat yuborish bosqichlari
│   └── admin.py                   # Qidiruv, biriktirish, javob berish holatlari
│
├── database/                      # Ma'lumotlar bazasi qatlami
│   ├── database.py                # Async engine, session va initsializatsiya
│   ├── models.py                  # SQLAlchemy 2.0 deklarativ modellari
│   ├── queries.py                 # Asinxron ma'lumotlar bazasi so'rovlari
│   └── migrations/                # Alembic avtomatik migratsiyalari
│
├── services/                      # Biznes logika xizmatlari
│   ├── application_service.py     # Murojaatlarni formatlash va tekshirish
│   ├── notification_service.py    # Tezkor Telegram bildirishnomalari
│   └── export_service.py          # Professional Excel (.xlsx) hisobot generatori
│
├── middlewares/                   # O'rta dasturlar
│   └── database.py                # Har bir so'rovga xavfsiz DB sessiyasini yetkazish
│
├── filters/                       # Filtrlar
│   └── admin_filter.py            # Rolga asoslangan ruxsat filtrlari
│
├── utils/                         # Yordamchi vositalar
│   ├── helpers.py                 # Sana, telefon formati, audit logging
│   └── number_generator.py        # AF-2026-000001 noyob raqam generatori
│
├── logs/                          # Tizim jurnallari (bot.log)
├── data/                          # Ma'lumotlar, SQLite bazasi, hisobotlar
└── test_system.py                 # 10 ta asosiy modulni tekshiruvchi avtomat test
```

---

### ⚙️ TEXNOLOGIK STEK

- **Dasturlash tili**: Python 3.12+ (Python 3.13 qo‘llab-quvvatlanadi).
- **Telegram Bot Framework**: aiogram 3.15+ (Asinxron, tezkor, FSM).
- **ORM / Baza boshqaruvi**: SQLAlchemy 2.0 Async + aiosqlite (Lokal) / asyncpg (PostgreSQL Production).
- **Migratsiyalar**: Alembic.
- **Konfiguratsiya va validatsiya**: Pydantic v2 & Pydantic-Settings.
- **Hisobotlar**: openpyxl (Stilli va jadvalli Excel fayllar).
- **FSM kesh / saqlash**: Redis (Redis mavjud bo‘lmaganda MemoryStorage rejimiga avtomatik o‘tadi).
- **Vaqt mintaqasi**: `Asia/Tashkent` (pytz orqali O‘zbekiston vaqti bilan qat'iy sinxron).

---

### 🚀 O‘RNATISH VA ISHGA TUSHIRISH

#### 1-USUL: Lokal kompyuterda ishga tushirish (Windows / Linux / macOS)

1. **Repozitoriyga kiring**:
   ```bash
   cd "c:\Users\JASURBEK\Desktop\E murojaat"
   ```

2. **Virtual muhitni faollashtiring**:
   - Windows PowerShell:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - Linux / macOS:
     ```bash
     source venv/bin/activate
     ```

3. **Kutubxonalarni tekshiring**:
   ```bash
   pip install -r requirements.txt
   ```

4. **.env faylini sozlang**:
   `.env` faylini ochib, o‘zingizning bot tokeningizni va Super Administrator Telegram ID raqamingizni kiriting:
   ```ini
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   SUPER_ADMIN_ID=123456789
   DATABASE_URL=sqlite+aiosqlite:///data/e_murojaat.db
   TIMEZONE=Asia/Tashkent
   APP_ENV=development
   ```

5. **Tizim testini o‘tkazib ko‘ring**:
   ```bash
   python test_system.py
   ```
   *Barcha 10 ta test muvaffaqiyatli o‘tishi kerak.*

6. **Botni ishga tushiring**:
   ```bash
   python bot.py
   ```

---

#### 2-USUL: Docker va Docker Compose orqali ishga tushirish (Production / VPS)

Eng ishonchli va tavsiya etiladigan usul. Birgina buyruq bilan PostgreSQL 16, Redis 7 va Bot alohida konteynerlarda ishga tushadi:

1. **.env faylida bot tokenini ko‘rsating**:
   ```ini
   BOT_TOKEN=o_zingizning_haqiqiy_tokeningiz
   SUPER_ADMIN_ID=o_zingizning_telegram_idingiz
   ```

2. **Konteynerlarni ishga tushiring**:
   ```bash
   docker compose up -d --build
   ```

3. **Holatni tekshirish**:
   ```bash
   docker compose ps
   docker compose logs -f bot
   ```

---

#### 3-USUL: Linux VPS (Ubuntu/Debian) da `systemd` orqali doimiy fonda yurgizish

1. VPS serverda loyihani `/opt/e-murojaat-bot` papkasiga joylashtiring.
2. Systemd service faylini yarating:
   ```bash
   sudo nano /etc/systemd/system/emurojaat.service
   ```
3. Quyidagi konfiguratsiyani kiriting:
   ```ini
   [Unit]
   Description=E-Murojaat Telegram Bot (Pedagogika fakulteti)
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/e-murojaat-bot
   ExecStart=/opt/e-murojaat-bot/venv/bin/python /opt/e-murojaat-bot/bot.py
   Restart=always
   RestartSec=5
   EnvironmentFile=/opt/e-murojaat-bot/.env

   [Install]
   WantedBy=multi-user.target
   ```
4. Servisni yoqing va ishga tushiring:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable emurojaat
   sudo systemctl start emurojaat
   sudo systemctl status emurojaat
   ```

---

### 📋 FOYDALANUVCHI VA ADMINISTRATOR YO‘RIQNOMASI

#### 👤 Foydalanuvchilar uchun:
1. **/start**: Botni ishga tushiradi. Birinchi kirishda toifa tanlanadi (Talaba, Fuqaro, Ota-ona, Xodim, Boshqa), kerakli maydonlar to‘ldiriladi va qonuniy maxfiylik roziligi beriladi.
2. **📝 Murojaat yuborish**: Murojaat turi, yo‘nalishi, mavzusi, batafsil mazmuni, fayllar va maxfiylik turi tanlanadi. Yakuniy tekshiruvdan so‘ng yuboriladi va unga `PF-2026-XXXXXX` raqami beriladi.
3. **📂 Mening murojaatlarim**: O‘zining barcha murojaatlari, ularning holatlari va javoblarini ko‘rish.
4. **🔎 Murojaat holatini tekshirish**: Murojaat raqami orqali tezkor tekshirish.
5. **💬 Dekanat bilan yozishmalar**: Murojaat bo‘yicha dekanatga qo‘shimcha ma'lumot yoki fayl yuborish.
6. **👤 Mening profilim**: Shaxsiy ma'lumotlarni ko‘rish va istalgan vaqtda tahrirlash.

#### 👑 Dekan va Administratorlar uchun (/admin):
1. **📥 Yangi murojaatlar**: Kelib tushgan murojaatlar ro‘yxati. Har bir murojaat ostida:
   - `👁 Batafsil ko‘rish`
   - `🔄 Ko‘rib chiqishga olish`
   - `👤 Mas'ulga biriktirish` (Fakultet mas'ul xodimini tanlash, ijro muddati va topshiriq izohini kiritish)
   - `📨 Javob yuborish` (Rasmiy javob yozish — javob darhol murojaatchi Telegramiga yetkaziladi)
   - `📝 Izoh qoldirish` (Ichki xizmat yozishmasi)
   - `✅ Hal qilindi`
   - `❌ Rad etish` (Majburiy rad etish sababi kiritiladi va foydalanuvchiga bildiriladi)
2. **👥 Xodimlarni boshqarish**: Yangi xodim qo‘shish (Telegram ID orqali), ularga Dekan, Administrator yoki Mas'ul xodim rollarini biriktirish, lavozimini belgilash yoki vakolatini bekor qilish.
3. **📊 Statistika va hisobotlar**: Kunlik, haftalik, oylik va umumiy ko‘rsatkichlar. Excel formatida `.xlsx` hisobotni bot orqali to‘g‘ridan-to‘g‘ri yuklab olish.
4. **📢 Xabar yuborish**: Bot foydalanuvchilariga umumiy e'lon va rasmiy xabarlarni tarqatish.
5. **⚙️ Bot sozlamalari**: Fakultet nomi, Dekan F.I.Sh., aloqa raqamlari, yo‘nalishlar va standart muddatlarni to‘g‘ridan-to‘g‘ri Telegram orqali o‘zgartirish hamda ma'lumotlar bazasi zaxirasini (Backup) olish.

---

### 🌐 UPTIMEROBOT ORQALI 24/7 UXLATMASDAN ISHLATISH (RENDER, KOYEB, RAILWAY)

Render, Koyeb yoki boshqa bepul serverlarda botlar 15 daqiqa faoliyatsizlikdan keyin "uxlab qolishi" (sleep mode) mumkin.
Buning oldini olish uchun bot tarkibiga maxsus **asinxron Keep-Alive HTTP veb-serveri** kiritilgan:
- Standart port: `8080` (yoki bulutli server bergan `$PORT` muhit o‘zgaruvchisi avtomatik olinadi).
- Manzillar: `/`, `/health` va `/ping` (barcha so‘rovlarga `200 OK` qaytaradi).

#### UptimeRobot orqali sozlash yo‘riqnomasi:
1. [UptimeRobot.com](https://uptimerobot.com) saytidan bepul ro‘yxatdan o‘ting.
2. **Add New Monitor** tugmasini bosing:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `E-Murojaat Bot`
   - **URL (or IP):** `https://sizning-botingiz.onrender.com/` (yoki `/health`)
   - **Monitoring Interval:** `5 minutes` (har 5 daqiqada so‘rov yuborib botni doim uyg‘oq saqlaydi)
3. **Create Monitor** tugmasini bosing.
   Tizim har 5 daqiqada serveringizga so‘rov yuborib, uning 24/7 uzluksiz ishlashini kafolatlaydi!

---

### 🛡 XAVFSIZLIK VA AUDIT

- Tizimda barcha harakatlar `audit_logs` jadvalida xavfsiz qayd etiladi.
- Maxfiy murojaatlar oddiy xodimlarga ko‘rsatilmaydi (backend darajasida filtrlangan).
- Foydalanuvchilar bir-birlarining murojaatlarini mutlaqo ko‘ra olmaydilar.
- SQL Injection, fayl kengaytmasi va hajmi cheklovlari to‘liq joriy etilgan.

---
**E-MUROJAAT** — Pedagogika fakultetining ishonchli, shaffof va zamonaviy elektron ko‘prigi!

