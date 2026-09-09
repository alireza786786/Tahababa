<div align="center">

# ⚡ V2Ray Config Collector & Tester ⚡

  <p align="center">
    <b>سیستم هوشمند دریافت، تست سلامت واقعی با Xray Core، استخراج موقعیت جغرافیایی و ارسال خودکار به تلگرام</b>
    <br />
    <a href="https://github.com/ebrasha/free-v2ray-public-list"><strong>مشاهده منبع کانفیگ‌ها »</strong></a>
    <br />
    <br />
    <img src="https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/YOUR_REPO/run.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=Workflow%20Status" alt="Workflow Status" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/Xray--Core-Latest-blue?style=for-the-badge&logo=v2ray&logoColor=white" alt="Xray Core" />
    <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
  </p>

---

</div>

## 📌 معرفی پروژه

این پروژه یک راه‌کار خودکار و قدرتمند مبتنی بر **GitHub Actions** و **Python AsyncIO** است که به‌صورت دوره‌ای (هر ۱۵ دقیقه) کانفیگ‌های V2Ray (VLESS, VMess, Trojan, ShadowSocks) را جمع‌آوری کرده، آن‌ها را با استفاده از هسته واقعی **Xray-Core** ارزیابی می‌کند و خروجی‌های سالم و مرتب‌شده را به کانال تلگرام ارسال می‌نماید.

---

## ✨ قابلیت‌های کلیدی

- 🚀 **تست سلامت واقعی با Xray Core:** برخلاف تست‌های معمولی TCP، تست اتصال و صحت عملکرد به‌وسیله خود موتور Xray سنجیده می‌شود.
- ⚡ **سرعت بالا (Async/Parallel):** پردازش همزمان ده‌ها کانفیگ با استفاده از `asyncio` و `aiohttp`.
- 📍 **شناسایی موقعیت جغرافیایی (GeoIP):** استخراج کشور، پرچم کشور و شهر سرورها با سیستم کش‌سازی هوشمند جهت جلوگیری از بن شدن IP.
- 🏷 **برچسب‌گذاری و تغییر برند (Remarking):** جایگزینی خودکار نام کانال و افزودن متاداده‌ها به نام کانفیگ با فرمت:
  `👉🆔@Channel📡🚩®️Country©️City🅿️ping:XXms`
- 💾 **سیستم کش باینری (Xray Cache):** ذخیره‌سازی هسته Xray بین اجراهای GitHub Actions برای افزایش چشمگیر سرعت اجرا.
- 🛡 **کنترل همزمانی (Concurrency Control):** جلوگیری از تداخل اجراها و مصرف بی‌رویه منابع گیت‌هاب.
- 📦 **تقسیم‌بندی و فشرده‌سازی:** تقسیم فایل‌های خروجی به پارت‌های سفارشی و بسته‌بندی زیپ جهت ارسال مستقیم به تلگرام.

---

## 🛠 معماری و نحوه کارکرد

```text
[ Sources / Raw Configs ]
           │
           ▼
[ Fetch & Deduplicate ]
           │
           ▼
[ Xray-Core Health Test ] ──► (Filter Latency > 250ms)
           │
           ▼
[ Batch GeoIP & Cache ]  ──► (SQLite Database)
           │
           ▼
[ Remark & Split Files ]
           │
           ▼
[ Zip Archive & Telegram Bot Upload ]
