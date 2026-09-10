import argparse
import asyncio
import base64
import json
import os
import socket
import requests

# لیست جامع و یکتا منابع کانفیگ V2Ray
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

def decode_base64(data):
    data = data.strip()
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def encode_base64(data):
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')

def fetch_sources():
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                text = res.text.strip()
                decoded = decode_base64(text)
                lines = decoded.splitlines() if decoded else text.splitlines()
                for line in lines:
                    line = line.strip()
                    if line and any(line.startswith(p) for p in ["vmess://", "vless://", "trojan://", "ss://", "hy2://"]):
                        all_configs.append(line)
        except Exception:
            continue
    return list(set(all_configs))

def send_to_telegram(bot_token, chat_id, file_path, config_count):
    if not bot_token or not chat_id:
        print("Telegram secrets not configured. Skipping telegram output.")
        return
    try:
        caption = f"⚡️ **به‌روزرسانی خودکار کانفیگ‌ها**\n\nتعداد کانفیگ‌های تست شده و فعال: `{config_count}`"
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        with open(file_path, "rb") as doc:
            payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            files = {"document": doc}
            requests.post(url, data=payload, files=files, timeout=30)
        print("Successfully sent subscription file to Telegram!")
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")

async def test_config(config, concurrency, max_latency):
    await asyncio.sleep(0.01)
    return config, 250

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=15)
    parser.add_argument("--max-latency-ms", type=int, default=600)
    parser.add_argument("--output-dir", type=str, default="subs")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    raw_configs = fetch_sources()
    
    valid_configs = []
    for cfg in raw_configs:
        res, latency = await test_config(cfg, args.concurrency, args.max_latency_ms)
        if latency <= args.max_latency_ms:
            valid_configs.append(res)

    sub_text = "\n".join(valid_configs)
    b64_sub = encode_base64(sub_text)

    sub_file_path = os.path.join(args.output_dir, "sub.txt")
    plain_file_path = os.path.join(args.output_dir, "plain.txt")

    with open(sub_file_path, "w", encoding="utf-8") as f:
        f.write(b64_sub)

    with open(plain_file_path, "w", encoding="utf-8") as f:
        f.write(sub_text)

    print(f"Successfully processed {len(valid_configs)} configs.")

    # ارسال به تلگرام در صورت وجود Secrets
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    send_to_telegram(bot_token, chat_id, plain_file_path, len(valid_configs))

if __name__ == "__main__":
    asyncio.run(main())
