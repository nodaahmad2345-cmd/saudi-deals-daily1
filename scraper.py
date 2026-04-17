"""
Saudi Deals Daily — Scraping Engine
====================================
يجلب عروض المتاجر السعودية ويخزنها في sites.json
"""

import asyncio
import json
import re
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FILE = Path("sites.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
}

# قائمة المتاجر
SITES = [
    {"name": "أمازون السعودية", "url": "https://www.amazon.sa/deals", "cat": "متعدد", "emoji": "📦", "bg": "#ff9900", "org": "عالمي"},
    {"name": "نون السعودية", "url": "https://www.noon.com/saudi-ar/sale/", "cat": "متعدد", "emoji": "🌙", "bg": "#feee00", "org": "خليجي"},
    {"name": "نمشي", "url": "https://sa.namshi.com/sale/", "cat": "أزياء", "emoji": "👗", "bg": "#000000", "org": "خليجي"},
    {"name": "إكسترا", "url": "https://www.extra.com.sa/ar/offers", "cat": "إلكترونيات", "emoji": "🖥️", "bg": "#e63946", "org": "سعودي"},
    {"name": "أيكيا السعودية", "url": "https://www.ikea.com/sa/ar/offers/", "cat": "منزل", "emoji": "🛋️", "bg": "#0058a3", "org": "عالمي"},
]

def extract_discount(text):
    patterns = [r'(\d+)\s*%\s*خصم', r'خصم\s*(\d+)\s*%', r'(\d+)\s*%\s*off']
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match: return int(match.group(1))
    return None

async def scrape_site(site):
    name = site["name"]
    url = site["url"]
    try:
        log.info(f"جاري فحص: {name}")
        # استخدام requests للمواقع البسيطة
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            site["discount"] = extract_discount(resp.text) or 30 # قيمة افتراضية إذا لم يجد
            site["active"] = True
            site["last_updated"] = datetime.now(timezone.utc).isoformat()
            log.info(f"✅ نجح جلب {name}")
        return site
    except Exception as e:
        log.error(f"❌ خطأ في {name}: {e}")
        site["active"] = False
        return site

async def main():
    tasks = [scrape_site(s) for s in SITES]
    results = await asyncio.gather(*tasks)
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "sites": results
    }
    
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"✅ تم تحديث {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
