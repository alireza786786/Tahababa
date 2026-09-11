import argparse
import asyncio
import base64
import json
import os
import re
import socket
import ssl
import time
import urllib.parse
import requests

SOURCES = [
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
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no3.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no4.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no5.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no6.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no7.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no8.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no9.txt",
    "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs_no10.txt",
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/yebekhe/TVC/main/subscriptions/xray/normal/mix",
    "https://raw.githubusercontent.com/yebekhe/TVC/main/subscriptions/xray/base64/mix",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray.txt",
    "https://raw.githubusercontent.com/erfan-zahhed/v2ray-configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/EbrahimAhar/V2Ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/IranianScanner/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/morteza-f-1990/v2ray-configs/main/sub.txt",
    "https://raw.githubusercontent.com/freev2rayconfig/V2RAY_FREE_CONFIG/main/sub.txt",
    "https://raw.githubusercontent.com/soroushmirzaei/telegram-v2ray-configs/main/sub/mix"
]

MY_CHANNEL = "@Goodbaye_filtering"
MY_CHAT_GROUP = "https://t.me/CONFIG_V2RAY_VIP"
GOLDEN_PORTS = {443, 80, 8080, 8880, 2052, 2082, 2086, 8443, 2053, 2083, 2087, 2096}
GEO_CACHE = {}

def decode_base64(data):
    data = data.strip().replace('\n', '').replace('\r', '')
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def encode_base64(data):
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')

def parse_host_port(config_str):
    try:
        if config_str.startswith("vmess://"):
            body = config_str[8:]
            decoded = decode_base64(body)
            obj = json.loads(decoded)
            return str(obj.get("add", "")), int(obj.get("port", 0))
        elif config_str.startswith("ss://"):
            body = config_str[5:].split("#")[0]
            if "@" in body:
                hostport = body.rsplit("@", 1)[1]
            else:
                decoded = decode_base64(body)
                hostport = decoded.rsplit("@", 1)[1] if "@" in decoded else ""
            if ":" in hostport:
                h = hostport.rpartition(":")[0]
                p = hostport.rpartition(":")[2]
                return h, int(p)
        else:
            parsed = urllib.parse.urlparse(config_str)
            if parsed.hostname and parsed.port:
                return parsed.hostname, int(parsed.port)
    except Exception:
        pass
    return None, None

def get_ip_info(host):
    if host in GEO_CACHE:
        return GEO_CACHE[host]
    try:
        ip = socket.gethostbyname(host)
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode,city", timeout=2).json()
        country = res.get("country", "Germany")
        country_code = res.get("countryCode", "DE")
        city = res.get("city", "Frankfurt am Main")
        flag = "".join(chr(127397 + ord(c)) for c in country_code.upper()) if len(country_code) == 2 else "🇩🇪"
        res_tuple = (flag, country, city)
        GEO_CACHE[host] = res_tuple
        return res_tuple
    except Exception:
        return "🇩🇪", "Germany", "Frankfurt am Main"

async def test_config_latency(host, port, timeout=1.8):
    if not host or not port:
        return None
    start = time.time()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        latency = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return latency
    except Exception:
        return None

def calculate_score(config_str, port, latency):
    score = 1000.0 - (latency if latency else 999.0)
    if port in GOLDEN_PORTS:
        score += 200
    if port == 443:
        score += 150
    if "pbk=" in config_str or "hysteria2://" in config_str or "hy2://" in config_str:
        score += 300
    return score

def format_config_remark(config_str, ping_ms):
    flag, country, city = "🇩🇪", "Germany", "Frankfurt am Main"
    remark = f"👉🆔{MY_CHANNEL}📡{flag}®️{country}©️{city}🅿️ping:{ping_ms:.0f}ms"
    
    if config_str.startswith("vmess://"):
        try:
            raw = decode_base64(config_str[8:])
            data = json.loads(raw)
            flag, country, city = get_ip_info(data.get("add", ""))
            data["ps"] = f"👉🆔{MY_CHANNEL}📡{flag}®️{country}©️{city}🅿️ping:{ping_ms:.0f}ms"
            return "vmess://" + encode_base64(json.dumps(data, ensure_ascii=False))
        except Exception:
            return config_str
    elif any(config_str.startswith(p) for p in ["vless://", "trojan://", "ss://", "hy2://", "hysteria2://"]):
        try:
            parsed = urllib.parse.urlparse(config_str)
            flag, country, city = get_ip_info(parsed.hostname or "")
            remark = f"👉🆔{MY_CHANNEL}📡{flag}®️{country}©️{city}🅿️ping:{ping_ms:.0f}ms"
            base_url = config_str.split('#')[0]
            return f"{base_url}#{urllib.parse.quote(remark)}"
        except Exception:
            return config_str
    return config_str

def fetch_and_deduplicate_sources():
    all_configs = []
    seen_hostports = set()
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=6)
            if res.status_code == 200:
                text = res.text.strip()
                decoded = decode_base64(text)
                lines = decoded.splitlines() if decoded else text.splitlines()
                for line in lines:
                    line = line.strip()
                    if line and any(line.startswith(p) for p in ["vmess://", "vless://", "trojan://", "ss://", "hy2://", "hysteria2://"]):
                        host, port = parse_host_port(line)
                        if host and port:
                            key = (host, port)
                            if key not in seen_hostports:
                                seen_hostports.add(key)
                                all_configs.append((line, host, port))
                        else:
                            core_config = line.split('#')[0]
                            if core_config not in seen_hostports:
                                seen_hostports.add(core_config)
                                all_configs.append((line, None, None))
        except Exception:
            continue
    return all_configs

def send_telegram_part(bot_token, chat_id, file_path, count):
    if not bot_token or not chat_id:
        print(f"⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing! Skipped sending {os.path.basename(file_path)}")
        return
    
    file_name = os.path.basename(file_path)
    caption = (
        f"🚀 <b>گلچین سرورهای پرسرعت (تست شده)</b>\n\n"
        f"📦 <b>نام فایل:</b> <code>{file_name}</code>\n"
        f"📌 <b>تعداد کانفیگ‌های سالم:</b> {count} عدد\n"
        f"⚡️ <b>وضعیت شبکه:</b> تست زنده TCP (پینگ زیر ۵۰۰ms) + پورت‌های طلایی\n\n"
        f"💬 <b>تبادل و چت:</b>\n{MY_CHAT_GROUP}\n\n"
        f"📅 <b>وضعیت به روزرسانی:</b> تایید شده ✅\n\n"
        f"✨ <b>منبع:</b>\nhttps://t.me/{MY_CHANNEL.replace('@', '')}"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as doc:
            payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            files = {"document": doc}
            res = requests.post(url, data=payload, files=files, timeout=30).json()
            if res.get("ok"):
                print(f"✅ Successfully sent {file_name} to Telegram.")
            else:
                print(f"❌ Telegram API Error: {res.get('description')}")
    except Exception as e:
        print(f"❌ Exception while sending {file_name}: {e}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default="subs")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    raw_configs = fetch_and_deduplicate_sources()
    
    semaphore = asyncio.Semaphore(50)
    tested_configs = []

    async def worker(item):
        cfg, host, port = item
        if not host or not port:
            return
        async with semaphore:
            latency = await test_config_latency(host, port)
            # فقط کانفیگ‌های با پینگ زیر ۵۰۰ میلی‌ثانیه تایید می‌شوند
            if latency is not None and latency < 500:
                score = calculate_score(cfg, port, latency)
                tested_configs.append({'config': cfg, 'latency': latency, 'score': score})

    tasks = [worker(item) for item in raw_configs]
    await asyncio.gather(*tasks)

    tested_configs.sort(key=lambda x: x['score'], reverse=True)

    processed_configs = []
    for item in tested_configs:
        formatted = format_config_remark(item['config'], item['latency'])
        processed_configs.append(formatted)

    full_text = "\n".join(processed_configs)
    
    with open(os.path.join(args.output_dir, "plain.txt"), "w", encoding="utf-8") as f:
        f.write(full_text)
    with open(os.path.join(args.output_dir, "sub.txt"), "w", encoding="utf-8") as f:
        f.write(encode_base64(full_text))

    part_size = 200
    chunks = [processed_configs[i:i + part_size] for i in range(0, len(processed_configs), part_size)]
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    for idx, chunk in enumerate(chunks, 1):
        file_name = f"subscription_part{idx}.txt"
        file_path = os.path.join(args.output_dir, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk))
        send_telegram_part(bot_token, chat_id, file_path, len(chunk))

    print(f"Successfully processed {len(processed_configs)} high-speed configs across {len(chunks)} parts.")

if __name__ == "__main__":
    asyncio.run(main())
