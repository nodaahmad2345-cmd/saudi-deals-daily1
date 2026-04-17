"""
Saudi Deals Daily — Scraping Engine
====================================
يجلب عروض المتاجر السعودية ويخزنها في sites.json
الاستخدام:  python scraper.py
المتطلبات:  pip install requests beautifulsoup4 playwright
            playwright install chromium
"""

import asyncio
import json
import re
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ── إعداد التسجيل ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── ثوابت ────────────────────────────────────────────────────────────────────
OUTPUT_FILE = Path("sites.json")
TIMEOUT     = 15          # ثانية
DELAY       = 1.5         # تأخير بين الطلبات لتجنب الحظر
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── قائمة المتاجر (مصدر الحقيقة — يمكن تحديثها هنا) ─────────────────────
SITES = [
    {"name": "أمازون السعودية",    "url": "https://www.amazon.sa/deals",                        "cat": "متعدد",      "emoji": "📦", "bg": "#ff9900", "org": "عالمي",  "desc": "أكبر متجر إلكتروني بعروض يومية حصرية وشحن سريع"},
    {"name": "نون السعودية",        "url": "https://www.noon.com/saudi-ar/sale/",                 "cat": "متعدد",      "emoji": "🌙", "bg": "#feee00", "org": "خليجي",  "desc": "المنصة الخليجية الأولى بعروض تصل حتى 70%"},
    {"name": "جوميا السعودية",      "url": "https://www.jumia.com.sa/deals/",                    "cat": "متعدد",      "emoji": "🛍️", "bg": "#f68b1e", "org": "عالمي",  "desc": "عروض يومية متنوعة على آلاف المنتجات"},
    {"name": "نمشي",               "url": "https://sa.namshi.com/sale/",                         "cat": "أزياء",      "emoji": "👗", "bg": "#000000", "org": "خليجي",  "desc": "أزياء وأحذية راقية بخصومات كبيرة"},
    {"name": "6thStreet",           "url": "https://en.6thstreet.com/sa/sale",                   "cat": "أزياء",      "emoji": "👟", "bg": "#e8001c", "org": "خليجي",  "desc": "أكثر من 500 ماركة عالمية بأسعار خيالية"},
    {"name": "وصف",                "url": "https://www.watsons.com.sa/ar/offers",                "cat": "جمال",       "emoji": "💄", "bg": "#e91e8c", "org": "عالمي",  "desc": "مستحضرات تجميل وعناية بالبشرة"},
    {"name": "ماكياج دوت كوم",      "url": "https://ar.makeup.com/sa/special-offers",             "cat": "جمال",       "emoji": "💅", "bg": "#c41e5c", "org": "عالمي",  "desc": "أكبر تشكيلة مستحضرات التجميل"},
    {"name": "سيفورا",              "url": "https://www.sephora.com/sa/ar/sale",                  "cat": "جمال",       "emoji": "🌸", "bg": "#000000", "org": "عالمي",  "desc": "أشهر متجر تجميل عالمي بعروض حصرية"},
    {"name": "كارفور السعودية",     "url": "https://www.carrefourksa.com/mafsau/ar/deals",        "cat": "بقالة",      "emoji": "🛒", "bg": "#004f9f", "org": "عالمي",  "desc": "تسوق أسبوعي بأسعار لا تقبل المنافسة"},
    {"name": "بنده",               "url": "https://www.bindawood.com/ar/offers",                 "cat": "بقالة",      "emoji": "🥬", "bg": "#008000", "org": "سعودي",  "desc": "سوبرماركت سعودي بعروض أسبوعية مميزة"},
    {"name": "إكس سايت",           "url": "https://www.xcite.com/sa-ar/deals",                  "cat": "إلكترونيات", "emoji": "📱", "bg": "#00aaff", "org": "خليجي",  "desc": "إلكترونيات وأجهزة بأفضل أسعار الخليج"},
    {"name": "اكس ستور",           "url": "https://www.extra.com.sa/ar/offers",                  "cat": "إلكترونيات", "emoji": "🖥️", "bg": "#e63946", "org": "سعودي",  "desc": "أكبر متجر إلكترونيات سعودي بعروض مستمرة"},
    {"name": "نايكي السعودية",      "url": "https://www.nike.com/sa/w/sale",                     "cat": "رياضة",      "emoji": "✔️", "bg": "#111111", "org": "عالمي",  "desc": "أحذية وملابس رياضية بتخفيضات موسمية كبيرة"},
    {"name": "أديداس السعودية",     "url": "https://www.adidas.com.sa/ar/sale",                  "cat": "رياضة",      "emoji": "⚽", "bg": "#000000", "org": "عالمي",  "desc": "ملابس وأحذية أديداس بأفضل أسعار السعودية"},
    {"name": "أيكيا السعودية",      "url": "https://www.ikea.com/sa/ar/offers/",                 "cat": "منزل",       "emoji": "🛋️", "bg": "#0058a3", "org": "عالمي",  "desc": "أثاث وديكور منزلي بأسعار مثالية"},
    {"name": "النهدي",              "url": "https://www.nahdi.sa/ar/offers",                     "cat": "صيدلية",     "emoji": "🏥", "bg": "#009b4e", "org": "سعودي",  "desc": "صيدلية سعودية كبرى — منتجات صحية وجمال"},
]

# ── أنماط الكشف عن العروض ─────────────────────────────────────────────────
DISCOUNT_PATTERNS = [
    r'(\d+)\s*%\s*(?:off|خصم|تخفيض|discount)',
    r'(?:خصم|تخفيض|off)\s*(\d+)\s*%',
    r'(?:وفر|save)\s*(\d+)\s*%',
    r'حتى\s*(\d+)\s*%',
    r'up\s+to\s+(\d+)\s*%',
]

DEAL_KEYWORDS = {
    "ar": ["عرض", "خصم", "تخفيض", "وفر", "تنزيلات", "سعر مميز", "sale", "حتى"],
    "en": ["sale", "deal", "off", "discount", "save", "offer", "clearance"],
}


# ══════════════════════════════════════════════════════════════════════════════
# وظائف المساعدة
# ══════════════════════════════════════════════════════════════════════════════

def check_url_status(url: str) -> dict:
    """يتحقق من حالة الرابط ويُعيد معلوماته."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT,
                          allow_redirects=True)
        return {
            "status":    r.status_code,
            "ok":        r.status_code < 400,
            "final_url": r.url,
            "redirect":  r.url != url,
        }
    except requests.exceptions.SSLError:
        # حاول بدون SSL
        try:
            r = requests.head(url, headers=HEADERS, timeout=TIMEOUT,
                              allow_redirects=True, verify=False)
            return {"status": r.status_code, "ok": r.status_code < 400,
                    "final_url": r.url, "redirect": False}
        except Exception as e:
            return {"status": 0, "ok": False, "final_url": url, "error": str(e)}
    except Exception as e:
        return {"status": 0, "ok": False, "final_url": url, "error": str(e)}


def extract_discount(text: str) -> int | None:
    """يستخرج أعلى نسبة خصم مذكورة في النص."""
    text_lower = text.lower()
    discounts = []
    for pattern in DISCOUNT_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        discounts.extend(int(m) for m in matches if m.isdigit())
    return max(discounts) if discounts else None


def extract_deal_count(soup: BeautifulSoup) -> int:
    """يحاول تقدير عدد العروض في الصفحة."""
    count = 0
    for kw in DEAL_KEYWORDS["ar"] + DEAL_KEYWORDS["en"]:
        count += len(soup.find_all(string=re.compile(kw, re.IGNORECASE)))
    return min(count, 999)   # حد أقصى منطقي


def extract_image(soup: BeautifulSoup, base_url: str) -> str | None:
    """يحاول استخراج صورة تمثيلية للعروض."""
    # OG image أولاً
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    # أول صورة منتج كبيرة
    for img in soup.find_all("img", src=True)[:20]:
        src = img["src"]
        if any(skip in src for skip in ["logo", "icon", "flag", "avatar"]):
            continue
        w = img.get("width") or img.get("data-width") or "0"
        try:
            if int(str(w).replace("px", "")) >= 100:
                return urljoin(base_url, src)
        except ValueError:
            pass

    return None


# ══════════════════════════════════════════════════════════════════════════════
# المجلب الرئيسي (Requests + BeautifulSoup)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_site_bs4(site: dict) -> dict:
    """يجلب بيانات متجر واحد باستخدام requests + BeautifulSoup."""
    url   = site["url"]
    name  = site["name"]
    result = {**site}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"[{attempt}/{MAX_RETRIES}] جلب {name} ← {url}")
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                                allow_redirects=True)
            result["http_status"] = resp.status_code
            result["final_url"]   = resp.url

            if resp.status_code == 404:
                result["active"] = False
                result["error"]  = "404 Not Found"
                return result

            if not resp.ok:
                result["active"] = False
                result["error"]  = f"HTTP {resp.status_code}"
                return result

            soup = BeautifulSoup(resp.text, "html.parser")

            # استخراج البيانات
            result["discount"]       = extract_discount(resp.text)
            result["deal_count"]     = extract_deal_count(soup)
            result["thumbnail"]      = extract_image(soup, url)
            result["active"]         = True
            result["last_checked"]   = datetime.now(timezone.utc).isoformat()
            result["last_updated"]   = datetime.now(timezone.utc).isoformat()

            # عنوان الصفحة (للتحقق)
            title_tag = soup.find("title")
            result["page_title"] = title_tag.get_text(strip=True) if title_tag else ""

            log.info(f"  ✅ {name} | خصم={result['discount']}% | عروض≈{result['deal_count']}")
            return result

        except requests.Timeout:
            log.warning(f"  ⚠️ انتهت مهلة {name} (محاولة {attempt})")
            time.sleep(DELAY * attempt)
        except Exception as exc:
            log.error(f"  ❌ خطأ في {name}: {exc}")
            result["error"]  = str(exc)
            result["active"] = False
            return result

    result["active"] = False
    result["error"]  = "تجاوز الحد الأقصى للمحاولات"
    return result


# ══════════════════════════════════════════════════════════════════════════════
# المجلب باستخدام Playwright (للمواقع التي تعتمد JS)
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_site_playwright(site: dict) -> dict:
    """يجلب بيانات متجر يعتمد على JavaScript باستخدام Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("Playwright غير مثبت — استخدام BS4 بدلاً منه")
        return scrape_site_bs4(site)

    url  = site["url"]
    name = site["name"]
    result = {**site}

    async with async_playwright() as p:
        # ── إعدادات Cloud/CI (GitHub Actions, Docker, ...) ──────────────
        browser = await p.chromium.launch(
            headless=True,                 # إلزامي في بيئة الـ Cloud
            args=[
                "--no-sandbox",            # ضروري في Linux/Docker
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", # يمنع مشاكل الذاكرة المؤقتة
                "--disable-gpu",           # لا GPU في السيرفر
                "--disable-extensions",
                "--no-first-run",
                "--no-zygote",
                "--single-process",        # أكثر استقراراً في CI
            ],
        )
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="ar-SA",
            extra_http_headers={"Accept-Language": "ar-SA,ar;q=0.9"},
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        try:
            log.info(f"[Playwright] جلب {name}")
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)     # انتظر تحميل JS

            content = await page.content()
            soup    = BeautifulSoup(content, "html.parser")

            result["discount"]     = extract_discount(content)
            result["deal_count"]   = extract_deal_count(soup)
            result["thumbnail"]    = extract_image(soup, url)
            result["active"]       = True
            result["final_url"]    = page.url
            result["last_checked"] = datetime.now(timezone.utc).isoformat()
            result["last_updated"] = datetime.now(timezone.utc).isoformat()

            title_tag = soup.find("title")
            result["page_title"] = title_tag.get_text(strip=True) if title_tag else ""

            log.info(f"  ✅ {name} | خصم={result['discount']}% | عروض≈{result['deal_count']}")

        except Exception as exc:
            log.error(f"  ❌ Playwright خطأ {name}: {exc}")
            result["error"]  = str(exc)
            result["active"] = False
        finally:
            await browser.close()

    return result


# ══════════════════════════════════════════════════════════════════════════════
# نظام إعادة التوجيه الذكي (Redirect System)
# ══════════════════════════════════════════════════════════════════════════════

def safe_redirect(url: str) -> dict:
    """
    يتحقق من الرابط قبل التوجيه:
    - يُعيد الرابط النهائي بعد إعادة التوجيه
    - يُبلّغ إذا كان الرابط معطوباً (404 / timeout / SSL)
    """
    info = check_url_status(url)
    return {
        "original_url": url,
        "safe":         info["ok"],
        "redirect_to":  info["final_url"] if info["ok"] else None,
        "http_status":  info["status"],
        "error":        info.get("error"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════════════════

def run_scraper(use_playwright_for: set[str] | None = None) -> list[dict]:
    """
    يشغّل المجلب على جميع المتاجر ويُعيد النتائج.
    
    use_playwright_for: أسماء المتاجر التي تحتاج Playwright
    """
    use_playwright_for = use_playwright_for or set()
    results = []

    js_sites    = [s for s in SITES if s["name"] in use_playwright_for]
    plain_sites = [s for s in SITES if s["name"] not in use_playwright_for]

    # ── المواقع العادية ─────────────────────────────────────────────────────
    for site in plain_sites:
        result = scrape_site_bs4(site)
        results.append(result)
        time.sleep(DELAY)

    # ── المواقع التي تعتمد JS ───────────────────────────────────────────────
    if js_sites:
        async def _run_all():
            tasks = [scrape_site_playwright(s) for s in js_sites]
            return await asyncio.gather(*tasks)
        results.extend(asyncio.run(_run_all()))

    # ── تصدير JSON ──────────────────────────────────────────────────────────
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total":        len(results),
        "sites":        results,
    }
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info(f"\n📁 تم الحفظ في {OUTPUT_FILE} ({len(results)} متجر)")
    return results


if __name__ == "__main__":
    import os
    is_ci = os.environ.get("CI", "false").lower() == "true"

    log.info("=" * 60)
    log.info("🚀 Saudi Deals Daily — Scraper Engine")
    if is_ci:
        log.info("☁️  تعمل في بيئة CI/Cloud (GitHub Actions)")
    log.info("=" * 60)

    # المتاجر التي تحتاج Playwright (تعتمد JS بالكامل):
    JS_SITES = {"أمازون السعودية", "نون السعودية"}

    run_scraper(use_playwright_for=JS_SITES)
