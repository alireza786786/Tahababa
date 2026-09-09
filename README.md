<div align="center">

# ⚡ V2Ray Config Collector & Tester ⚡

  <p align="center">
    <b>سیستم هوشمند دریافت، تست سلامت واقعی با Xray Core، استخراج موقعیت جغرافیایی و ارسال خودکار به تلگرام</b>
    <br />
    <a href="https://github.com/ebrasha/free-v2ray-public-list"><strong>مشاهده منبع کانفیگ‌ها »</strong></a>
    <br />
    <br />
    <img src="https://img.shields.io/github/actions/workflow/status/alireza786786/Tahababa/run.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=Workflow%20Status" alt="Workflow Status" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/Xray--Core-Latest-blue?style=for-the-badge&logo=v2ray&logoColor=white" alt="Xray Core" />
    <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
  </p>

---

</div>

## 📌 معرفی پروژه

این پروژه یک راه‌کار خودکار و قدرتمند مبتنی بر **GitHub Actions** و **Python AsyncIO** است که به‌صورت دوره‌ای (هر ۱۵ دقیقه) کانفیگ‌های V2Ray را جمع‌آوری کرده، آن‌ها را با استفاده از هسته واقعی **Xray-Core** ارزیابی می‌کند و خروجی‌های سالم را در ۳ لینک سابسکرایب مجزا قرار داده و نسخه زیپ آن را به تلگرام ارسال می‌نماید.

---

## 📡 لینک‌های سابسکرایب مستقیم (Subscription Links)

شما می‌توانید لینک‌های زیر را مستقیماً کپی کرده و وارد نرم‌افزارهای خود (v2rayNG, Streisand, Shadowrocket, NekoBox و...) کنید. این لینک‌ها هر **۱۵ دقیقه** به‌صورت خودکار آپدیت می‌شوند:

| بخش | سهم کانفیگ‌ها | لینک سابسکرایب (جهت کپی در برنامه) |
| :---: | :---: | :--- |
| 🚀 **پارت اول** | ۳۳٪ کل | `https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/subscription_part1.txt` |
| ⚡ **پارت دوم** | ۳۳٪ کل | `https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/subscription_part2.txt` |
| 🔥 **پارت سوم** | ۳۴٪ کل | `https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/subscription_part3.txt` |

---

## ✨ قابلیت‌های کلیدی

- 🚀 **تست سلامت واقعی با Xray Core:** ارزیابی واقعی اتصال به‌وسیله موتور Xray به‌جای پینگ ساده TCP.
- ⚡ **سرعت بالا (Async/Parallel):** پردازش همزمان ده‌ها کانفیگ با استفاده از `asyncio` و `aiohttp`.
- 📍 **شناسایی موقعیت جغرافیایی (GeoIP):** استخراج کشور، پرچم کشور و شهر سرورها با سیستم کش‌سازی هوشمند.
- 🏷 **برچسب‌گذاری و تغییر برند (Remarking):** جایگزینی خودکار نام کانال و افزودن متاداده‌ها با فرمت:
  `👉🆔@Goodbaye_filtering📡🚩®️Country©️City🅿️ping:XXms`
- 📊 **تقسیم متوازن به ۳ لینک:** توزیع دقیق کانفیگ‌های سالم بین ۳ فایل سابسکرایب مجزا.
- 📦 **فشرده‌سازی و ارسال به تلگرام:** بسته‌بندی فایل‌ها به صورت ZIP و ارسال مستقیم به کانال/چت تلگرام.

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
[ Remark & Split into 3 Parts ]
           │
           ├──────────────────────────────┐
           ▼                              ▼
[ Update Subscription Links ]    [ Send ZIP to Telegram ]
