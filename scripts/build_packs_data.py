#!/usr/bin/env python3
"""
این اسکریپت توسط ربات گیت‌هاب (GitHub Actions) هر ۱ ساعت یکبار اجرا می‌شه.
کارش اینه که پوشه‌ی Pack رو بررسی کنه، برای هر زیرپوشه (هر پک) دنبال
زیرپوشه‌های Java و Bedrock بگرده، و آدرس فایل زیپ داخلشون رو پیدا کنه.
نتیجه‌ی نهایی توی فایل packs-data.json کنار index.html ذخیره می‌شه.
سایت (index.html) فقط همین فایل رو می‌خونه و هیچ درخواستی به API گیت‌هاب نمی‌زنه.
"""

import base64
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

REPO = os.environ["GITHUB_REPOSITORY"]  # به‌صورت خودکار توسط Actions پر می‌شه: owner/repo
TOKEN = os.environ["GITHUB_TOKEN"]
API_BASE = f"https://api.github.com/repos/{REPO}/contents"


def api_get(path):
    """گرفتن محتوای یک مسیر از مخزن گیت‌هاب. اگه پیدا نشد None برمی‌گردونه."""
    url = f"{API_BASE}/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "pack-bot",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


# پسوندهای فایلی که به‌عنوان فایل قابل‌دانلود پک شناخته می‌شن
ARCHIVE_EXTENSIONS = (
    ".zip",
    ".rar",
    ".7z",
    ".mcpack",
    ".mcaddon",
    ".mcworld",
)


def find_archive(items):
    """پیدا کردن اولین فایل قابل‌دانلود (با هر کدوم از پسوندهای بالا) داخل یک لیست از آیتم‌های گیت‌هاب."""
    if not isinstance(items, list):
        return None
    for item in items:
        name = item.get("name", "").lower()
        if item.get("type") == "file" and name.endswith(ARCHIVE_EXTENSIONS):
            return item.get("download_url")
    return None


def find_first_file(items):
    """پیدا کردن اولین فایل (با هر پسوندی) داخل یک لیست از آیتم‌های گیت‌هاب. برای پوشه File مودها استفاده می‌شه."""
    if not isinstance(items, list):
        return None
    for item in items:
        if item.get("type") == "file":
            return item.get("download_url")
    return None


def get_text_file(path):
    """خوندن محتوای یک فایل متنی (مثل Help.txt) از مخزن. اگه نبود None برمی‌گردونه."""
    data = api_get(path)
    if not isinstance(data, dict) or data.get("type") != "file":
        return None

    content_b64 = data.get("content")
    if content_b64:
        try:
            text = base64.b64decode(content_b64).decode("utf-8", errors="replace").strip()
            return text or None
        except Exception:
            return None

    # اگه فایل خیلی بزرگ بود و API محتوا رو نداد، از لینک خام بخونش
    download_url = data.get("download_url")
    if download_url:
        try:
            req = urllib.request.Request(download_url, headers={"User-Agent": "pack-bot"})
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode("utf-8", errors="replace").strip()
                return text or None
        except Exception:
            return None

    return None


def build_packs():
    """بررسی پوشه Pack و ساخت لیست ریسورس پک‌ها (با دو نسخه جاوا/بدراک)."""
    root = api_get("Pack")
    packs = []

    if isinstance(root, list):
        dirs = [
            item for item in root
            if item.get("type") == "dir" and not item.get("name", "").startswith(".")
        ]
        for d in dirs:
            name = d["name"]
            encoded = urllib.parse.quote(name)

            java_items = api_get(f"Pack/{encoded}/Java")
            bedrock_items = api_get(f"Pack/{encoded}/Bedrock")
            description = get_text_file(f"Pack/{encoded}/Help.txt")

            packs.append({
                "name": name,
                "java": find_archive(java_items),
                "bedrock": find_archive(bedrock_items),
                "description": description,
            })

    return packs


def build_mods():
    """بررسی پوشه Mod و ساخت لیست مودها (هرکدوم با یک فایل دانلود داخل پوشه File)."""
    root = api_get("Mod")
    mods = []

    if isinstance(root, list):
        dirs = [
            item for item in root
            if item.get("type") == "dir" and not item.get("name", "").startswith(".")
        ]
        for d in dirs:
            name = d["name"]
            encoded = urllib.parse.quote(name)

            file_items = api_get(f"Mod/{encoded}/File")
            description = get_text_file(f"Mod/{encoded}/Help.txt")
            compatibility = get_text_file(f"Mod/{encoded}/Job.txt")

            mods.append({
                "name": name,
                "file": find_first_file(file_items),
                "description": description,
                "compatibility": compatibility,
            })

    return mods


def build_shaders():
    """بررسی پوشه Shader و ساخت لیست شیدرها (هرکدوم با یک فایل دانلود داخل پوشه File)."""
    root = api_get("Shader")
    shaders = []

    if isinstance(root, list):
        dirs = [
            item for item in root
            if item.get("type") == "dir" and not item.get("name", "").startswith(".")
        ]
        for d in dirs:
            name = d["name"]
            encoded = urllib.parse.quote(name)

            file_items = api_get(f"Shader/{encoded}/File")
            description = get_text_file(f"Shader/{encoded}/Help.txt")
            compatibility = get_text_file(f"Shader/{encoded}/Job.txt")

            shaders.append({
                "name": name,
                "file": find_first_file(file_items),
                "description": description,
                "compatibility": compatibility,
            })

    return shaders


def build_films():
    """بررسی پوشه Film و ساخت لیست فیلم‌ها (هرکدوم با یک لینک داخل پوشه Link)."""
    root = api_get("Film")
    films = []

    if isinstance(root, list):
        dirs = [
            item for item in root
            if item.get("type") == "dir" and not item.get("name", "").startswith(".")
        ]
        for d in dirs:
            name = d["name"]
            encoded = urllib.parse.quote(name)

            description = get_text_file(f"Film/{encoded}/Help.txt")

            link_url = None
            link_items = api_get(f"Film/{encoded}/Link")
            if isinstance(link_items, list):
                txt_file = next((i for i in link_items if i.get("type") == "file"), None)
                if txt_file:
                    txt_name = urllib.parse.quote(txt_file["name"])
                    link_text = get_text_file(f"Film/{encoded}/Link/{txt_name}")
                    if link_text:
                        link_url = link_text.strip()

            films.append({
                "name": name,
                "description": description,
                "link": link_url,
            })

    return films


def main():
    packs = build_packs()
    mods = build_mods()
    shaders = build_shaders()
    films = build_films()

    data = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "packs": packs,
        "mods": mods,
        "shaders": shaders,
        "films": films,
    }

    with open("packs-data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"انجام شد. {len(packs)} پک، {len(mods)} مود، {len(shaders)} شیدر و {len(films)} فیلم پیدا شد.")


if __name__ == "__main__":
    main()
