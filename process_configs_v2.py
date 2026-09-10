    asyncio.run(main())
import asyncio
import argparse
import json
import os
import re
import sqlite3
import subprocess
import urllib.parse
import base64
import socket
from pathlib import Path
import aiohttp

# --- ۱. دریافت ورودی‌های خط فرمان ---
parser = argparse.ArgumentParser(description="Ultimate V2Ray Collector & Real HTTP Tester")
parser.add_argument("--url", default="", help="URL to fetch configs")
parser.add_argument("--channel-name", default="@Goodbaye_filtering", help="Telegram channel name")
parser.add_argument("--concurrency", type=int, default=15, help="Parallel Xray checks")
parser.add_argument("--max-latency-ms", type=int, default=600, help="Strict max allowed latency in ms")
parser.add_argument("--output-dir", default="outputs", help="Directory to save output files")
args = parser.parse_args()

CHANNEL_NAME = args.channel_name
NUM_PARTS = 3
CONCURRENCY_LIMIT = args.concurrency
MAX_LATENCY_MS = args.max_latency_ms
OUTPUT_DIR = Path(args.output_dir)
XRAY_BIN = Path("./.xray_bin/xray")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_FILE = "history.db"

ALLOWED_COUNTRIES = {'DE', 'NL', 'FI', 'US', 'GB', 'FR', 'CA', 'SG', 'JP', 'SE', 'CH', 'AT', 'PL'}

PRIORITY_PORTS = {
    443: 1, 8443: 1, 2053: 1, 2083: 1, 2087: 1, 2096: 1,
    80: 2, 8080: 2, 8880: 2, 2052: 2, 2082: 2, 2086: 2
}

RAW_SOURCES = [
    "https://raw.githubusercontent.com/MrAbolfazlNorouzi/iran-configs/refs/heads/main/configs/working-configs.txt",
    "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/mix/sub.html",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_BASE64.txt",
    "https://manager.onetwothree123.ir/",
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/top100.txt",
    "https://raw.githubusercontent.com/Q3dlaXpoaQ/Q3dlaXpoaQ.github.io/refs/heads/main/APIs/cg1.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mci/sub_1.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_1.txt",
    "https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/refs/heads/main/configs/ir/vless.txt",
    "https://raw.githubusercontent.com/Surfboardv2ray/TGParse/refs/heads/main/splitted/hysteria2",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/vless.txt"
]

if args.url:
    RAW_SOURCES.insert(0, args.url)

SOURCES = list(dict.fromkeys(RAW_SOURCES))

# --- توابع کمکی Base64 & Geo ---
def b64_decode(s: str) -> str:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad).decode(errors="ignore")

def b64_encode(s: str) -> str:
    return base64.b64encode(s.encode()).decode()

def country_code_to_flag(code):
    if not code or len(code) != 2:
        return "🌐"
    code = code.upper()
    return chr(127397 + ord(code[0])) + chr(127397 + ord(code[1]))

def resolve_host(host: str) -> str:
    """تبدیل دامنه به IP برای دقت بیشتر در لوکیشن‌یابی"""
    if not host:
        return host
    try:
        return socket.gethostbyname(host)
    except Exception:
        return host

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS geo_cache (ip TEXT PRIMARY KEY, country TEXT, country_code TEXT, city TEXT)")
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
        decoded = b64_decode(text)
        if any(proto in decoded for proto in ['vless://', 'vmess://', 'trojan://', 'ss://', 'hy2://']):
            return decoded
    except Exception:
        pass
    return text

def detect_operators(config):
    config_lower = config.lower()
    port = extract_port(config)
    operators = []
    if "reality" in config_lower or config_lower.startswith("hy2://") or config_lower.startswith("hysteria2://"):
        operators.extend(["MCI", "MTN"])
    if port in [443, 8443, 2053, 2083]:
        operators.extend(["MCI", "MTN", "RTL", "WiFi"])
    elif port in [80, 8080, 8880]:
        operators.extend(["WiFi", "MTN"])
    if "mci" in config_lower: operators.append("MCI")
    if "mtn" in config_lower or "irancell" in config_lower: operators.append("MTN")
    
    unique_ops = list(dict.fromkeys(operators))
    return "|".join(unique_ops) if unique_ops else "ALL"

def extract_port(config):
    try:
        if config.startswith("vmess://"):
            data = json.loads(b64_decode(config[8:]))
            return int(data.get("port", 0))
        else:
            match = re.search(r':(\d+)(?=[?#/]|$)', config)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return 0

def extract_ip_or_host(config):
    try:
        if config.startswith("vmess://"):
            data = json.loads(b64_decode(config[8:]))
            return resolve_host(data.get("add"))
        elif config.startswith("ss://"):
            body = config.split("ss://", 1)[1].split("#")[0]
            if "@" in body:
                return resolve_host(body.split("@")[1].split(":")[0])
        else:
            match = re.search(r'@([^:\s/?#]+)', config)
            if match:
                return resolve_host(match.group(1))
    except Exception:
        pass
    return None

# --- بازنویسی پیشرفته نام کانفیگ‌ها ---
def advanced_remark_config(config, latency, channel, geo_info):
    country, country_code, city = geo_info if geo_info else ("Unknown", "XX", "Unknown")
    flag = country_code_to_flag(country_code)
    ops = detect_operators(config)
    tag = f"👉🆔{channel}📡{flag}®️{country}⚡️{ops}🅿️ping:{latency}ms"

    try:
        if config.startswith("vmess://"):
            data = json.loads(b64_decode(config[8:]))
            data["ps"] = tag
            return f"vmess://{b64_encode(json.dumps(data, ensure_ascii=False))}#{urllib.parse.quote(tag)}"
        
        elif config.startswith("ss://"):
            body = config.split("ss://", 1)[1].split("#")[0]
            return f"ss://{body}#{urllib.parse.quote(tag)}"
            
        else:
            base_url = config.split('#')[0]
            return f"{base_url}#{urllib.parse.quote(tag)}"
    except Exception:
        return config

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
                            cache_geo(item.get("query"), item.get("country", "Unknown"), item.get("countryCode", "XX"), item.get("city", "Unknown"))
            except Exception:
                pass

async def test_config_real_http(semaphore, config, local_port):
    async with semaphore:
        if not XRAY_BIN.exists(): return None
        config_file = Path(f"temp_{local_port}.json")
        xray_config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": local_port, "listen": "127.0.0.1", "protocol": "socks"}],
            "outbounds": [{"protocol": "freedom"}]
        }
        with open(config_file, "w") as f: json.dump(xray_config, f)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(str(XRAY_BIN), "run", "-c", str(config_file), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(0.4)

            proxy_url = f"http://127.0.0.1:{local_port}"
            timeout = aiohttp.ClientTimeout(total=4.0)
            
            start_time = asyncio.get_event_loop().time()
            async with aiohttp.ClientSession(timeout=timeout) as test_session:
                async with test_session.get("https://www.gstatic.com/generate_204", proxy=proxy_url) as resp:
                    if resp.status in (200, 204):
                        end_time = asyncio.get_event_loop().time()
                        latency = int((end_time - start_time) * 1000)
                        if latency > MAX_LATENCY_MS: return None

                        # تست دانلود فایل واقعی (۵۰۰KB)
                        speed_url = "https://speed.cloudflare.com/__down?bytes=500000"
                        async with test_session.get(speed_url, proxy=proxy_url) as dl_resp:
                            if dl_resp.status == 200:
                                await dl_resp.read()
                                return config, latency
        except Exception:
            pass
        finally:
            if proc:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception: pass
            if config_file.exists(): config_file.unlink()

        return None

async def main():
    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_configs = []
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers={"User-Agent": "Mozilla/5.0"}) as session:
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
                print(f"Error source {src}: {e}")

        unique_raw_configs = list(dict.fromkeys(raw_configs))
        print(f"\nTotal Unique Configs to Test: {len(unique_raw_configs)}")

        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        tasks = [test_config_real_http(semaphore, cfg, 10000 + (idx % 1000)) for idx, cfg in enumerate(unique_raw_configs)]
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if r is not None]
        print(f"✅ Active Configs Passed Download Test: {len(valid_results)}")

        hosts = list(set([extract_ip_or_host(cfg) for cfg, _ in valid_results if extract_ip_or_host(cfg)]))
        await fetch_geo_info(session, hosts)

        filtered_results = []
        for cfg, lat in valid_results:
            host = extract_ip_or_host(cfg)
            geo = get_cached_geo(host) if host else None
            country_code = geo[1] if geo else "XX"
            if country_code in ALLOWED_COUNTRIES or country_code == "XX":
                filtered_results.append((cfg, lat, geo))

        filtered_results.sort(key=lambda x: (PRIORITY_PORTS.get(extract_port(x[0]), 3), x[1]))

        final_configs = [advanced_remark_config(cfg, lat, CHANNEL_NAME, geo) for cfg, lat, geo in filtered_results]

        # ذخیره خروجی‌ها
        all_configs_str = "\n".join(final_configs)
        with open(OUTPUT_DIR / "sub.txt", "w", encoding="utf-8") as f:
            f.write(base64.b64encode(all_configs_str.encode('utf-8')).decode('utf-8'))

        part_size = (len(final_configs) + NUM_PARTS - 1) // NUM_PARTS if final_configs else 0
        for part_num in range(1, NUM_PARTS + 1):
            chunk = final_configs[(part_num - 1) * part_size : min(part_num * part_size, len(final_configs))]
            if chunk:
                with open(OUTPUT_DIR / f"subscription_part{part_num}.txt", "w", encoding="utf-8") as f:
                    f.write(f"# Channel: {CHANNEL_NAME} - Part {part_num}\n" + "\n".join(chunk))

        print("✨ Process Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
