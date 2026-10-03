import base64
import json
import threading
import uuid
import yaml
import os
import time
import requests
from colorama import Fore, Style, init
from datetime import datetime, UTC
from tlsmask import Session

init()

with open("config.yml", "r") as file:
    config = yaml.safe_load(file)

def timestamp():
    return datetime.now(UTC).strftime("%H:%M:%S")

def success(content):
    print(f"{Fore.LIGHTBLACK_EX}{timestamp()} {Fore.LIGHTGREEN_EX}SUCCESS {Fore.WHITE}>{Fore.LIGHTBLACK_EX} {content}{Style.RESET_ALL}")

def error(content):
    print(f"{Fore.LIGHTBLACK_EX}{timestamp()} {Fore.LIGHTRED_EX}ERROR {Fore.WHITE}>{Fore.LIGHTBLACK_EX} {content}{Style.RESET_ALL}")

def warn(content):
    print(f"{Fore.LIGHTBLACK_EX}{timestamp()} {Fore.LIGHTYELLOW_EX}WARN {Fore.WHITE}>{Fore.LIGHTBLACK_EX} {content}{Style.RESET_ALL}")

def inp(prompt):
    return input(f"{Fore.LIGHTBLACK_EX}{timestamp()} {Fore.LIGHTMAGENTA_EX}INPUT {Fore.WHITE}>{Fore.LIGHTBLACK_EX} {prompt}{Style.RESET_ALL} ")

def build_xsup() -> str:
    data = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "has_client_mods": False,
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "browser_version": "152.0.0.0",
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": 625378,
        "client_event_source": None,
        "client_launch_id": f"{uuid.uuid4()}",
        "launch_signature": f"{uuid.uuid4()}",
        "client_heartbeat_session_id": f"{uuid.uuid4()}",
        "client_app_state": "unfocused"
    }
    return base64.b64encode(
        json.dumps(data, separators=(",", ":")).encode()
    ).decode()
def _solve_anysolver(proxy: str, rqdata: str) -> str:
    api_key = config["solver"]["api_key"]
    subservice = config["solver"]["subservice"]

    r = requests.post(
        "https://api.anysolver.com/createTask",
        json={
            "clientKey": api_key,
            "task": {
                "type": "PopularCaptchaEnterpriseToken",
                "websiteURL": "https://discord.com/register",
                "websiteKey": "a9b5fb07-92ff-493f-86fe-352a2803b3df",
                "proxy": proxy,
                "rqdata": rqdata
            },
            "settings": {
                "routing": {
                    "provider": subservice
                }
            }
        },
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    data = r.json()
    if data.get("errorId") != 0:
        raise RuntimeError(f"{data.get('errorCode')}: {data.get('errorDescription')}")

    task_id = data["taskId"]
    timeout = config.get("captcha_timeout", 120)
    start = time.time()
    time.sleep(4)

    while True:
        res = requests.post(
            "https://api.anysolver.com/getTaskResult",
            json={"clientKey": api_key, "taskId": task_id},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        result = res.json()
        status = result.get("status")

        if status == "ready":
            token = result["solution"]["token"]
            success(f"Captcha Solved in {time.time() - start:.1f}s ({token[:32]}...)")
            return token

        if status == "failed":
            raise RuntimeError(f"Captcha failed: {result.get('errorCode')} - {result.get('errorDescription')}")

        if time.time() - start > timeout:
            raise TimeoutError("Captcha solve timed out")

        time.sleep(3)

def _solve_ragecaptcha(proxy: str, rqdata: str) -> str:
    api_key = config["solver"]["api_key"]

    r = requests.post(
        "https://api.ragecaptcha.com/create-task",
        json={
            "clientkey": api_key,
            "data": {
                "task": "PopularCaptchaEnterpriseToken",
                "sitekey": "a9b5fb07-92ff-493f-86fe-352a2803b3df",
                "siteurl": "https://discord.com/register",
                "proxy": proxy,
                "rqdata": rqdata
            }
        },
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    data = r.json()
    if r.status_code != 202:
        raise RuntimeError(f"RageCaptcha create-task failed: {data}")

    task_id = data["task_id"]
    timeout = config.get("captcha_timeout", 120)
    start = time.time()
    time.sleep(3)

    while True:
        res = requests.post(
            "https://api.ragecaptcha.com/check-task",
            json={"clientkey": api_key, "task_id": task_id},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        result = res.json()
        status = result.get("status")

        if status == "success":
            token = result["solution"]
            success(f"Captcha Solved in {time.time() - start:.1f}s ({token[:32]}...)")
            return token

        if status == "failed":
            raise RuntimeError(f"Captcha failed: {result.get('error')}")

        if time.time() - start > timeout:
            raise TimeoutError("Captcha solve timed out")

        time.sleep(2)

def solver(proxy: str, rqdata: str) -> str:
    service = config["solver"].get("service", "anysolver").lower()
    if service == "ragecaptcha":
        return _solve_ragecaptcha(proxy, rqdata)
    return _solve_anysolver(proxy, rqdata)

def bot_add(token, guild_id, bot_id, proxy=None):
    session = Session(client_identifier="chrome_152")

    if proxy:
        p = proxy if proxy.startswith("http") else f"http://{proxy}"
        session.proxies = {"http": p, "https": p}

    session.cookies = session.get("https://discord.com/api/v9/experiments").cookies

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.7",
        "authorization": token,
        "content-type": "application/json",
        "origin": "https://discord.com",
        "priority": "u=1, i",
        "referer": "https://discord.com/channels/@me",
        "sec-ch-ua": '"Google Chrome";v="152", "Not_A Brand";v="8", "Chromium";v="152"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sec-gpc": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "x-debug-options": "bugReporterEnabled",
        "x-discord-locale": "en-US",
        "x-discord-timezone": "Asia/Karachi",
        "x-installation-id": f"{__import__('random').randrange(10**18, 10**19)}.{__import__('secrets').token_urlsafe(32)}",
        "x-super-properties": build_xsup(),
    }

    payload = {
        "guild_id": guild_id,
        "permissions": "8",
        "authorize": True,
        "integration_type": 0
    }

    url = f"https://discord.com/api/v9/oauth2/authorize?client_id={bot_id}&scope=bot%20applications.commands"
    response = session.post(url=url, headers=headers, json=payload)

    if response.status_code == 200:
        success(f"Bot {bot_id} added to {guild_id}")

    elif response.status_code == 400:
        warn("Captcha Encountered")
        captcha_data = response.json()

        try:
            response_key = solver(
                proxy=proxy,
                rqdata=captcha_data["captcha_rqdata"]
            )
        except Exception as e:
            error(str(e))
            return

        headers["x-captcha-key"] = response_key
        headers["x-captcha-rqtoken"] = captcha_data["captcha_rqtoken"]

        retry = session.post(url=url, headers=headers, json=payload)
        if retry.status_code == 200:
            success(f"Bot {bot_id} added to {guild_id} | Captcha Solved")
        else:
            error(f"Failed after captcha: {retry.text}")
    else:
        error(f"Failed: {response.text}")

def worker(token, guild_id, bot_ids, proxy=None):
    for bot_id in bot_ids:
        bot_add(token, guild_id, bot_id, proxy=proxy)
        time.sleep(2)

def main():
    os.system("cls" if os.name == "nt" else "clear")
    token = config["token"]
    guild_id = inp("Enter Server ID: ")

    botid_path = os.path.join("io", "botid.txt")
    proxy_path = os.path.join("io", "proxies.txt")

    if not os.path.exists(botid_path):
        error("io/botid.txt not found")
        return

    with open(botid_path, "r") as f:
        bot_ids = [line.strip() for line in f if line.strip()]

    proxies = []
    if os.path.exists(proxy_path):
        with open(proxy_path, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]

    bot_count = int(inp(f"How many bots to add (max {len(bot_ids)}): "))

    if bot_count > len(bot_ids):
        error("Not enough bot IDs in io/botid.txt")
        return

    thread_count = config["threads"]
    chunk_size = (bot_count + thread_count - 1) // thread_count
    threads = []

    for i in range(thread_count):
        start = i * chunk_size
        end = min(start + chunk_size, bot_count)
        if start >= bot_count:
            break
        proxy = proxies[i % len(proxies)] if proxies else None
        t = threading.Thread(target=worker, args=(token, guild_id, bot_ids[start:end], proxy))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()