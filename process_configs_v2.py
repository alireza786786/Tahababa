import asyncio
import argparse
import json
import os
import re
import sqlite3
import subprocess
import zipfile
import urllib.parse
from pathlib import Path
import aiohttp

# --- ۱. دریافت ورودی‌های خط فرمان ---
parser = argparse.ArgumentParser(description="Advanced V2Ray Collector & Tester")
parser.add_argument("--url", default="https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt", help="URL to fetch configs")
parser.add_argument("--channel-name", default="@Goodbaye_filtering", help="Telegram channel name")
parser.add_argument("--concurrency", type=int, default=20, help="Parallel TCP/Xray checks")
parser.add_argument("--max-latency-ms", type=int, default=250, help="Max allowed latency in ms")
parser.add_argument("--zip", action="store_true", help="Create zip archive of output")
parser.add_argument("--output-dir", default="outputs", help="Directory to save output files")
args = parser.parse_args()

# --- تنظیمات ---
CONFIG_URL = args.url
CHANNEL_NAME = args.channel_name
NUM_PARTS = 3
CONCURRENCY_LIMIT = args.concurrency
MAX_LATENCY_MS = args.max_latency_ms
OUTPUT_DIR = Path(args.output_dir)
XRAY_BIN = Path("./.xray_bin/xray")

# دریافت ایمن از متغیرهای محیطی
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_FILE = "history.db"

def country_code_to_flag(code):
    if not code or len(code) != 2:
        return "🌐"
    code = code.upper()
    return chr(127397 + ord(code[0])) + chr(127397 + ord(code[1]))

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS geo_cache (
            ip TEXT PRIMARY KEY,
            country TEXT,
            country_code TEXT,
            city TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_cached_geo(ip):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT country, country_code, city FROM geo_cache WHERE ip = ?", (ip,))
    row = cursor.fetchone()
    conn.close()
    return row

def cache_geo(ip, country, country_code, city):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO geo_cache VALUES (?, ?, ?, ?)", (ip, country, country_code, city))
    conn.commit()
    conn.close()

def extract_ip_or_host(config):
    match = re.search(r'@([^:\s/?#]+)', config)
    if match:
        return match.group(1)
    return None

async def fetch_geo_info(session, ips):
    ips_to_fetch = [ip for ip in ips if not get_cached_geo(ip)]
    if ips_to_fetch:
        for i in range(0, len(ips_to_fetch), 50):
            chunk = ips_to_fetch[i:i+50]
            try:
                async with session.post("http://ip-api.com/batch", json=chunk, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data:
                            ip = item.get("query")
                            country = item.get("country", "Unknown")
                            country_code = item.get("countryCode", "XX")
                            city = item.get("city", "Unknown")
                            cache_geo(ip, country, country_code, city)
            except Exception as e:
                print(f"Geo Fetch Error: {e}")

async def test_config(semaphore, config, port):
    async with semaphore:
        if not XRAY_BIN.exists():
            return None

        config_file = Path(f"temp_{port}.json")
        xray_config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": port, "listen": "127.0.0.1", "protocol": "socks"}],
            "outbounds": [{"protocol": "freedom"}]
        }
        
        with open(config_file, "w") as f:
            json.dump(xray_config, f)

        try:
            start_time = asyncio.get_event_loop().time()
            proc = await asyncio.create_subprocess_exec(
                str(XRAY_BIN), "run", "-c", str(config_file),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            await asyncio.sleep(0.3)
            end_time = asyncio.get_event_loop().time()
            latency = int((end_time - start_time) * 1000)

            proc.terminate()
            await proc.wait()

            if config_file.exists():
                config_file.unlink()

            if latency <= MAX_LATENCY_MS:
                return config, latency
        except Exception:
            if config_file.exists():
                config_file.unlink()
        return None

def remark_config(config, latency, channel, geo_info):
    country, country_code, city = geo_info if geo_info else ("Unknown", "XX", "Unknown")
    flag = country_code_to_flag(country_code)
    
    new_remark = f"👉🆔{channel}📡{flag}®️{country}©️{city}🅿️ping:{latency}ms"
    encoded_remark = urllib.parse.quote(new_remark)

    if '#' in config:
        base_url = config.split('#')[0]
        return f"{base_url}#{encoded_remark}"
    else:
        return f"{config}#{encoded_remark}"

async def send_zip_to_telegram(session, zip_path, total_count):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets not found. Skipping Telegram upload.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    
    caption_text = (
        f"✨ **پک جدید کانفیگ‌های تست شده**\n"
        f"📢 کانال: {CHANNEL_NAME}\n"
        f"📊 کل کانفیگ‌های سالم: `{total_count}` (تقسیم شده در ۳ فایل سابسکرایب)"
    )

    data = aiohttp.FormData()
    data.add_field('chat_id', TELEGRAM_CHAT_ID)
    data.add_field('caption', caption_text)
    data.add_field('parse_mode', 'Markdown')
    data.add_field('document', open(zip_path, 'rb'), filename=zip_path.name)

    try:
        async with session.post(url, data=data) as resp:
            resp_text = await resp.text()
            if resp.status == 200:
                print("ZIP file sent to Telegram successfully!")
            else:
                print(f"Telegram API Response: {resp_text}")
    except Exception as e:
        print(f"Error uploading to Telegram: {e}")

async def main():
    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        print(f"Fetching configs from: {CONFIG_URL}")
        async with session.get(CONFIG_URL) as resp:
            if resp.status != 200:
                print("Failed to fetch configs URL")
                return
            text = await resp.text()

        raw_configs = list(set(re.findall(r'(vless|vmess|trojan|ss|hy2)://[^\s]+', text)))
        print(f"Total Unique Configs: {len(raw_configs)}")

        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = [test_config(semaphore, cfg, 10000 + (idx % 1000)) for idx, cfg in enumerate(raw_configs)]
        results = await asyncio.gather(*tasks)
        valid_results = [r for r in results if r is not None]

        print(f"Valid Tested Configs: {len(valid_results)}")

        hosts = list(set([extract_ip_or_host(cfg) for cfg, _ in valid_results if extract_ip_or_host(cfg)]))
        await fetch_geo_info(session, hosts)

        final_configs = []
        for cfg, lat in valid_results:
            host = extract_ip_or_host(cfg)
            geo = get_cached_geo(host) if host else ("Unknown", "XX", "Unknown")
            final_configs.append(remark_config(cfg, lat, CHANNEL_NAME, geo))

        generated_files = []
        total_configs = len(final_configs)
        part_size = (total_configs + NUM_PARTS - 1) // NUM_PARTS if total_configs > 0 else 0

        for part_num in range(1, NUM_PARTS + 1):
            start_idx = (part_num - 1) * part_size
            end_idx = min(start_idx + part_size, total_configs)
            chunk = final_configs[start_idx:end_idx]

            file_path = OUTPUT_DIR / f"subscription_part{part_num}.txt"
            content = f"# Channel: {CHANNEL_NAME} - Part {part_num}/{NUM_PARTS}\n" + "\n".join(chunk)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            generated_files.append(file_path)

        zip_path = OUTPUT_DIR / "processed_configs.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in generated_files:
                zipf.write(file, file.name)
        
        print(f"ZIP file created with 3 parts: {zip_path}")
        await send_zip_to_telegram(session, zip_path, total_configs)

if __name__ == "__main__":
    asyncio.run(main())
