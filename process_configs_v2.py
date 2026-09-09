#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_configs_v2.py

- Tailored for large VLESS lists.
- Removes duplicates (by endpoint and by id/UUID when applicable).
- Concurrent TCP checks (fast); optional ICMP (--icmp).
- Batch geolocation via ip-api.com/batch with caching (includes city).
- Replaces other channel names with provided channel name.
- Adds suffix: 👉🆔{channel}📡{flag}®️{country}©️{city}🅿️ping:{ms}ms
- Splits output into subscription_part{n}.txt with header.
- Optionally zips outputs and sends only the zip to Telegram.
- Sends files (or zip) to Telegram using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (env or args).
"""
import argparse
import re
import requests
import socket
import subprocess
import os
import sys
import time
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, quote_plus
from datetime import datetime

VLESS_RE = re.compile(r'vless://([^@]+)@([^:/\s]+):(\d+)(?:\S*)#?(.*)', re.IGNORECASE)
IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
PORT_RE = re.compile(r'[:@]\s*(\d{2,5})\b|port[:=]\s*(\d{2,5})', re.IGNORECASE)
OTHER_CHANNEL_RE = re.compile(r'(@[\w\-]+|channel[:=]\s*\S+|#\s*channel[:=]?\s*\S+)', re.IGNORECASE)

# include city field
IP_API_BATCH = "http://ip-api.com/batch?fields=status,country,countryCode,city,query"

def to_flag_emoji(country_code):
    if not country_code or len(country_code) != 2:
        return ''
    offset = ord('\U0001F1E6') - ord('A')
    return chr(ord(country_code[0].upper()) + offset) + chr(ord(country_code[1].upper()) + offset)

def fetch_text(url, timeout=30):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text

def parse_vless_line(line):
    m = VLESS_RE.search(line.strip())
    if not m:
        return None
    uuid = m.group(1)
    host = m.group(2)
    port = int(m.group(3))
    remark = unquote(m.group(4)) if m.group(4) else ''
    return {"type":"vless", "raw": line.strip(), "uuid": uuid, "host": host, "port": port, "remark": remark}

def extract_host_port_from_block(text):
    ip_m = IP_RE.search(text)
    host = None
    if ip_m:
        host = ip_m.group(0)
    else:
        parts = re.findall(r'([a-zA-Z0-9\-.]+\.[a-zA-Z]{2,})', text)
        host = parts[0] if parts else None
    port = None
    m = PORT_RE.search(text)
    if m:
        port = m.group(1) or m.group(2)
    return host, (int(port) if port else None)

def tcp_check(host, port, timeout=3):
    start = time.perf_counter()
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        elapsed = (time.perf_counter() - start) * 1000.0
        return True, elapsed
    except Exception:
        return False, None

def icmp_ping(host, count=3, timeout=2):
    try:
        res = subprocess.run(['ping', '-c', str(count), '-W', str(timeout), host],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=(count*(timeout+1)+5))
        if res.returncode == 0:
            m = re.search(r'rtt .* = [\d\.]+/([\d\.]+)/', res.stdout)
            avg = float(m.group(1)) if m else None
            return True, avg
        return False, None
    except Exception:
        return False, None

class GeoBatcher:
    def __init__(self, batch_size=100, pause_between=1.5):
        self.batch_size = batch_size
        self.pause_between = pause_between
        self.cache = {}  # ip -> (country, code, city)

    def lookup_many(self, ips):
        to_query = [ip for ip in sorted(set(ips)) if ip and ip not in self.cache]
        for i in range(0, len(to_query), self.batch_size):
            batch = to_query[i:i+self.batch_size]
            try:
                resp = requests.post(IP_API_BATCH, json=batch, timeout=15)
                data = resp.json()
                for entry in data:
                    ip = entry.get('query')
                    if entry.get('status') == 'success':
                        self.cache[ip] = (entry.get('country'), entry.get('countryCode'), entry.get('city'))
                    else:
                        self.cache[ip] = (None, None, None)
                time.sleep(self.pause_between)
            except Exception:
                for ip in batch:
                    self.cache[ip] = (None, None, None)
        results = {}
        for ip in ips:
            results[ip] = self.cache.get(ip, (None, None, None))
        return results

def replace_channel_in_vless(raw, new_channel):
    m = VLESS_RE.search(raw)
    if not m:
        if raw.strip().endswith('#'):
            return raw.strip() + new_channel
        return raw.strip() + '#' + new_channel
    prefix = raw.split('#',1)[0]
    return prefix + '#' + quote_plus(new_channel)

def replace_channel_generic(text, new_channel):
    text2 = OTHER_CHANNEL_RE.sub('', text)
    text2 = text2.strip()
    if '# channel:' in text2.lower():
        text2 = re.sub(r'(?i)#\s*channel:.*', f'# channel: {new_channel}', text2)
    else:
        text2 = text2 + f'\n# channel: {new_channel}'
    return text2

def process_list(lines, args):
    parsed = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        pv = parse_vless_line(raw)
        if pv:
            parsed.append(pv)
        else:
            host, port = extract_host_port_from_block(raw)
            parsed.append({"type":"block", "raw": raw, "host": host, "port": port})
    # dedupe by uuid and endpoint
    seen_endpoints = set()
    seen_ids = set()
    unique = []
    for item in parsed:
        endpoint = None
        if item.get('host') and item.get('port'):
            endpoint = f"{item['host']}:{item['port']}"
        if item.get('type') == 'vless' and item.get('uuid'):
            if item['uuid'] in seen_ids:
                continue
            seen_ids.add(item['uuid'])
        if endpoint:
            if endpoint in seen_endpoints:
                continue
            seen_endpoints.add(endpoint)
        unique.append(item)
    # resolve hosts to ip
    for item in unique:
        host = item.get('host')
        ip = None
        if host:
            try:
                ip = socket.gethostbyname(host)
            except Exception:
                ip = None
        item['ip'] = ip
    # concurrent checks
    geo_ips = []
    def worker_check(it):
        host = it.get('host')
        port = it.get('port')
        if not host or not port:
            return (it, False, None, False, None)
        tcp_ok, tcp_ms = tcp_check(host, port, timeout=args.tcp_timeout)
        icmp_ok, icmp_ms = (False, None)
        if args.icmp and host:
            icmp_ok, icmp_ms = icmp_ping(host, count=2, timeout=1)
        return (it, tcp_ok, tcp_ms, icmp_ok, icmp_ms)
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        future_to_item = {ex.submit(worker_check, it): it for it in unique}
        for fut in as_completed(future_to_item):
            try:
                res = fut.result()
            except Exception:
                continue
            item, tcp_ok, tcp_ms, icmp_ok, icmp_ms = res
            item['tcp_ok'] = tcp_ok
            item['tcp_ms'] = tcp_ms
            item['icmp_ok'] = icmp_ok
            item['icmp_ms'] = icmp_ms
            results.append(item)
            if item.get('ip'):
                geo_ips.append(item['ip'])
    # geolocate
    geo = GeoBatcher(batch_size=args.geo_batch_size, pause_between=args.geo_pause)
    geo_map = geo.lookup_many(geo_ips)
    for it in results:
        ip = it.get('ip')
        if ip:
            country, code, city = geo_map.get(ip, (None,None,None))
            it['country'] = country
            it['country_code'] = code
            it['country_city'] = city
            it['flag'] = to_flag_emoji(code) if code else ''
        else:
            it['country'] = None
            it['country_code'] = None
            it['country_city'] = None
            it['flag'] = ''
    # classify and build modified
    active = []
    inactive = []
    for it in results:
        tcp_ok = bool(it.get('tcp_ok'))
        tcp_ms = it.get('tcp_ms') or None
        icmp_ok = bool(it.get('icmp_ok'))
        icmp_ms = it.get('icmp_ms') or None
        is_active = False
        is_very_good = False
        if tcp_ok and (tcp_ms is not None) and tcp_ms <= args.max_latency_ms:
            is_active = True
            is_very_good = True
        elif tcp_ok:
            is_active = True
        elif icmp_ok and (icmp_ms is not None) and icmp_ms <= args.max_latency_ms:
            is_active = True
            is_very_good = True
        if is_active:
            # choose ping value (TCP preferred)
            ping_value = tcp_ms if tcp_ms is not None else icmp_ms
            ping_str = f"{ping_value:.2f}" if ping_value is not None else "N/A"
            if it['type'] == 'vless':
                new_raw = replace_channel_in_vless(it['raw'], args.channel_name)
            else:
                new_raw = replace_channel_generic(it['raw'], args.channel_name)
            country = it.get('country') or ''
            city = it.get('country_city') or ''
            flag = it.get('flag') or ''
            channel_label = args.channel_name
            suffix = f" 👉🆔{channel_label}📡{flag}®️{country}©️{city}🅿️ping:{ping_str}ms"
            new_raw = new_raw + "  " + suffix
            it['modified'] = new_raw
            it['very_good'] = is_very_good
            active.append(it)
        else:
            it['modified'] = it['raw']
            inactive.append(it)
    return active, inactive

def write_outputs(active, inactive, args):
    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    safe_ch = args.channel_name.replace('@','').replace('/','_')
    very_good = [i for i in active if i.get('very_good')]
    not_so_good = [i for i in active if not i.get('very_good')]
    ordered = very_good + not_so_good
    files = []
    # write active in chunks named subscription_part{n}.txt with header
    part_idx = 0
    def header_text(part_no, count):
        return ("🔥 *اشتراک هوشمند - پارت {p}*\n\n"
                "📦 فایل: `subscription_part{p}.txt`\n"
                "📊 تعداد: *{c}* کانفیگ تست‌شده\n\n"
                "💬 گروه: {group}\n"
                "✨ کانال: {channel}\n\n").format(p=part_no, c=count, group=args.group_link, channel=args.channel_link)
    for start in range(0, len(ordered), args.split_size):
        part_idx += 1
        chunk = ordered[start:start+args.split_size]
        path = os.path.join(args.output_dir, f"subscription_part{part_idx}.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(header_text(part_idx, len(chunk)))
            for it in chunk:
                f.write(it.get('modified').rstrip() + "\n\n")
        files.append(path)
    # inactive files (chunked)
    part_idx_i = 0
    for start in range(0, len(inactive), args.split_size):
        part_idx_i += 1
        chunk = inactive[start:start+args.split_size]
        path = os.path.join(args.output_dir, f"inactive_part{part_idx_i}.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"🔥 Inactive - part {part_idx_i}\n\n")
            for it in chunk:
                f.write(it.get('modified').rstrip() + "\n\n")
        files.append(path)
    # report
    report_path = os.path.join(args.output_dir, f"report_{safe_ch}_{ts}.txt")
    with open(report_path, 'w', encoding='utf-8') as rf:
        rf.write(f"Total input approximated: {args.input_count}\n")
        rf.write(f"Active kept: {len(ordered)} (very_good: {len(very_good)})\n")
        rf.write(f"Inactive removed: {len(inactive)}\n")
    files.append(report_path)
    return files

def send_to_telegram(files, bot_token, chat_id):
    url = f'https://api.telegram.org/bot{bot_token}/sendDocument'
    results = []
    for p in files:
        with open(p,'rb') as fh:
            files_payload = {'document': (os.path.basename(p), fh)}
            data = {'chat_id': chat_id}
            r = requests.post(url, data=data, files=files_payload, timeout=120)
            results.append((p, r.status_code, r.text))
            time.sleep(1)
    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', required=True)
    p.add_argument('--channel-name', required=True)
    p.add_argument('--output-dir', default='outputs')
    p.add_argument('--split-size', type=int, default=300, help='max configs per file')
    p.add_argument('--concurrency', type=int, default=100, help='parallel TCP checks')
    p.add_argument('--tcp-timeout', type=int, default=3)
    p.add_argument('--icmp', action='store_true', help='also run ICMP ping (may be slow or blocked)')
    p.add_argument('--max-latency-ms', type=int, default=250, help='max latency to be considered very good')
    p.add_argument('--bot-token', required=False)
    p.add_argument('--chat-id', required=False)
    p.add_argument('--zip', action='store_true', help='zip outputs and send only zip')
    p.add_argument('--group-link', default='https://t.me/CONFIG_V2RAY_VIP', help='group link to include in header')
    p.add_argument('--channel-link', default='https://t.me/Goodbaye_filtering', help='channel link to include in header')
    p.add_argument('--geo-batch-size', type=int, default=100, help='ip-api batch size')
    p.add_argument('--geo-pause', type=float, default=1.5, help='pause between geo batches (s)')
    args = p.parse_args()

    # map args for geo class
    args.geo_batch_size = args.geo_batch_size if hasattr(args, 'geo_batch_size') else args.geo_batch_size
    args.geo_pause = args.geo_pause if hasattr(args, 'geo_pause') else args.geo_pause

    args.bot_token = args.bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
    args.chat_id = args.chat_id or os.getenv('TELEGRAM_CHAT_ID')
    print("[+] Downloading", args.url)
    text = fetch_text(args.url)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    args.input_count = len(lines)
    print(f"[+] Read {len(lines)} lines")
    active, inactive = process_list(lines, args)
    print(f"[+] Active: {len(active)}  Inactive: {len(inactive)}")
    files = write_outputs(active, inactive, args)
    print(f"[+] Wrote {len(files)} files to {args.output_dir}")
    if args.zip:
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        zip_name = os.path.join(args.output_dir, f"outputs_{ts}")
        shutil.make_archive(zip_name, 'zip', args.output_dir)
        zip_path = zip_name + '.zip'
        print(f"[+] Created zip: {zip_path}")
        if args.bot_token and args.chat_id:
            print("[+] Sending zip to Telegram...")
            res = send_to_telegram([zip_path], args.bot_token, args.chat_id)
            for p, code, text in res:
                print(f" -> {p}: {code}")
        else:
            print("[!] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; skipping send.")
    else:
        if args.bot_token and args.chat_id:
            print("[+] Sending files to Telegram...")
            res = send_to_telegram(files, args.bot_token, args.chat_id)
            for p, code, text in res:
                print(f" -> {p}: {code}")
        else:
            print("[!] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; skipping send.")
    print("[+] Done.")

if __name__ == "__main__":
    main()
