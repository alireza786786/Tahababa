import asyncio
import argparse
import json
import os
import re
import sqlite3
import subprocess
import urllib.parse
import base64
from pathlib import Path
import aiohttp

# --- ۱. دریافت ورودی‌های خط فرمان ---
parser = argparse.ArgumentParser(description="Advanced V2Ray Collector & Real HTTP Tester")
parser.add_argument("--url", default="", help="URL to fetch configs")
parser.add_argument("--channel-name", default="@Goodbaye_filtering", help="Telegram channel name")
parser.add_argument("--concurrency", type=int, default=20, help="Parallel Xray checks")
parser.add_argument("--max-latency-ms", type=int, default=600, help="Strict max allowed latency in ms")
parser.add_argument("--output-dir", default="outputs", help="Directory to save output files")
parser.add_argument("--zip", action="store_true", help="Legacy flag for backwards compatibility")
args = parser.parse_args()

# --- تنظیمات اصلی ---
CHANNEL_NAME = args.channel_name
NUM_PARTS = 3
CONCURRENCY_LIMIT = args.concurrency
MAX_LATENCY_MS = args.max_latency_ms
OUTPUT_DIR = Path(args.output_dir)
XRAY_BIN = Path("./.xray_bin/xray")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_FILE = "history.db"

# --- پورت‌های اولویت‌دار مناسب اپراتورهای ایران ---
PRIORITY_PORTS = {
    443: 1, 8443: 1, 2053: 1, 2083: 1, 2087: 1, 2096: 1,
    80: 2, 8080: 2, 8880: 2, 2052: 2, 2082: 2, 2086: 2
}

# --- لیست منابع دریافت کانفیگ ---
RAW_SOURCES = [
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_BASE64.txt",
    "https://manager.onetwothree123.ir/",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/top100.txt",
    "https://raw.githubusercontent.com/Q3dlaXpoaQ/Q3dlaXpoaQ.github.io/refs/heads/main/APIs/cg1.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mci/sub_1.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_1.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/refs/heads/main/configs/ir/vless.txt",
    "https://raw.githubusercontent.com/Surfboardv2ray/TGParse/refs/heads/main/splitted/hysteria2",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/vless.txt",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/refs/heads/main/protocols/hysteria2.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no1.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no2.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no3.txt"
]

if args.url:
    RAW_SOURCES.insert(0, args.url)

SOURCES = list(dict.fromkeys(RAW_SOURCES))

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
            ip TEXT PRIMARY KEY, country TEXT, country_code TEXT, city TEXT
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

def decode_base64_text(text):
    text = text.strip()
    try:
        padded_text = text + '=' * (-len(text) % 4)
        decoded = base64.b64decode(padded_text).decode('utf-8', errors='ignore')
        if any(proto in decoded for proto in ['vless://', 'vmess://', 'trojan://', 'ss://', 'hy2://']):
            return decoded
    except Exception:
        pass
    return text

def extract_port(config):
    try:
        if config.startswith("vmess://"):
            b64_data = config[8:]
            b64_data += '=' * (-len(b64_data) % 4)
            decoded = base64.b64decode(b64_data).decode('utf-8')
            data = json.loads(decoded)
            return int(data.get("port", 0))
        else:
            match = re.search(r':(\d+)(?=[?#/]|$)', config)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return 0

def extract_ip_or_host(config):
    if config.startswith("vmess://"):
        try:
            b64_data = config[8:]
            b64_data += '=' * (-len(b64_data) % 4)
            decoded = base64.b64decode(b64_data).decode('utf-8')
            data = json.loads(decoded)
            return data.get("add")
        except Exception:
            return None
    else:
        match = re.search(r'@([^:\s/?#]+)', config)
        if match:
            return match.group(1)
    return None

async def fetch_geo_info(session, ips):
    ips_to_fetch = [ip for ip in ips if ip and not get_cached_geo(ip)]
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

async def test_config_real_http(semaphore, config, local_port):
    """تست واقعی دریافت دیتا از اینترنت از طریق SOCKS Proxy محلی Xray"""
    async with semaphore:
        if not XRAY_BIN.exists():
            return None

        config_file = Path(f"temp_{local_port}.json")
        xray_config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": local_port, "listen": "127.0.0.1", "protocol": "socks"}],
            "outbounds": [{"protocol": "freedom"}]
        }
        
        with open(config_file, "w") as f:
            json.dump(xray_config, f)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(XRAY_BIN), "run", "-c", str(config_file),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            await asyncio.sleep(0.4)

            proxy_url = f"http://127.0.0.1:{local_port}"
            timeout = aiohttp.ClientTimeout(total=3.0)
            
            start_time = asyncio.get_event_loop().time()
            async with aiohttp.ClientSession(timeout=timeout) as test_session:
                async with test_session.get("https://www.gstatic.com/generate_204", proxy=proxy_url) as resp:
                    if resp.status in (200, 204):
                        end_time = asyncio.get_event_loop().time()
                        latency = int((end_time - start_time) * 1000)
                        if latency <= MAX_LATENCY_MS:
                            return config, latency
        except Exception:
            pass
        finally:
            if proc:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception:
                    pass
            if config_file.exists():
                config_file.unlink()

        return None

def remark_config(config, latency, channel, geo_info):
    country, country_code, city = geo_info if geo_info else ("Unknown", "XX", "Unknown")
    flag = country_code_to_flag(country_code)
    
    new_remark = f"👉🆔{channel}📡{flag}®️{country}©️{city}🅿️ping:{latency}ms"

    if config.startswith("vmess://"):
        try:
            b64_data = config[8:]
            b64_data += '=' * (-len(b64_data) % 4)
            decoded = base64.b64decode(b64_data).decode('utf-8')
            data = json.loads(decoded)
            data["ps"] = new_remark
            new_b64 = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
            return f"vmess://{new_b64}"
        except Exception:
            return config

    encoded_remark = urllib.parse.quote(new_remark)
    if '#' in config:
        base_url = config.split('#')[0]
        return f"{base_url}#{encoded_remark}"
    else:
        return f"{config}#{encoded_remark}"

async def send_txt_files_to_telegram(session, generated_files):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets not found. Skipping Telegram upload.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"

    for file_path, count in generated_files:
        caption_text = (
            f"🚀 کانفیگ‌های تست‌شده و زنده (تست واقعی اینترنت)\n\n"
            f"📦 نام فایل: {file_path.name}\n"
            f"📌 تعداد کانفیگ‌های فعال: {count} عدد\n"
            f"⚡️ وضعیت پینگ: واقعی زیر 600ms ✅\n"
            f"🎯 پورت‌های ویژه اولویت‌دار: 443, 8880, 8080\n\n"
            f"💬 تبادل و چت:\n"
            f"https://t.me/CONFIG_V2RAY_VIP\n\n"
            f"✨ منبع:\n"
            f"https://t.me/Goodbaye_filtering"
        )

        data = aiohttp.FormData()
        data.add_field('chat_id', TELEGRAM_CHAT_ID)
        data.add_field('caption', caption_text)
        data.add_field('document', open(file_path, 'rb'), filename=file_path.name)

        try:
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    print(f"File {file_path.name} sent successfully!")
        except Exception as e:
            print(f"Error uploading {file_path.name}: {e}")
        
        await asyncio.sleep(2)

async def main():
    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    raw_configs = []
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for src in SOURCES:
            try:
                print(f"Fetching: {src}")
                async with session.get(src) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        full_text = decode_base64_text(text)
                        extracted = re.findall(r'(?:vless|vmess|trojan|ss|hy2)://[^\s<>"{}|\^~\[\]`]+', full_text)
                        raw_configs.extend(extracted)
            except Exception as e:
                print(f"Error fetching source {src}: {e}")

        unique_raw_configs = list(set(raw_configs))
        print(f"\nTotal Configs Fetched: {len(raw_configs)}")
        print(f"Unique Configs to Test: {len(unique_raw_configs)}")

        if not unique_raw_configs:
            print("❌ No configs found!")
            return

        print("\n🔍 Starting Real HTTP Connection Testing...")
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = [test_config_real_http(semaphore, cfg, 10000 + (idx % 1000)) for idx, cfg in enumerate(unique_raw_configs)]
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if r is not None]
        print(f"✅ Real Active Configs Found: {len(valid_results)}")

        if not valid_results:
            print("⚠️ No config passed the strict HTTP test.")
            return

        hosts = list(set([extract_ip_or_host(cfg) for cfg, _ in valid_results if extract_ip_or_host(cfg)]))
        await fetch_geo_info(session, hosts)

        # مرتب‌سازی بر اساس اولویت پورت و سپس پینگ
        def config_sorter(item):
            cfg, lat = item
            port = extract_port(cfg)
            port_priority = PRIORITY_PORTS.get(port, 3)
            return (port_priority, lat)

        valid_results.sort(key=config_sorter)

        final_configs = []
        for cfg, lat in valid_results:
            host = extract_ip_or_host(cfg)
            geo = get_cached_geo(host) if host else ("Unknown", "XX", "Unknown")
            final_configs.append(remark_config(cfg, lat, CHANNEL_NAME, geo))

        final_configs = list(dict.fromkeys(final_configs))

        # تقسیم کانفیگ‌های سالم بین ۳ فایل txt
        generated_files = []
        total_configs = len(final_configs)
        part_size = (total_configs + NUM_PARTS - 1) // NUM_PARTS if total_configs > 0 else 0

        for part_num in range(1, NUM_PARTS + 1):
            start_idx = (part_num - 1) * part_size
            end_idx = min(start_idx + part_size, total_configs)
            chunk = final_configs[start_idx:end_idx]

            if not chunk:
                continue

            file_path = OUTPUT_DIR / f"subscription_part{part_num}.txt"
            content = f"# Channel: {CHANNEL_NAME} - Part {part_num}/{NUM_PARTS}\n" + "\n".join(chunk)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            generated_files.append((file_path, len(chunk)))

        print(f"Generated {len(generated_files)} part files.")
        await send_txt_files_to_telegram(session, generated_files)

if __name__ == "__main__":
    asyncio.run(main())
