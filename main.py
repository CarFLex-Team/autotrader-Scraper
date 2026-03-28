from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
import requests
import json
import re
import warnings
import time
import html as html_lib
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

warnings.filterwarnings("ignore")
app = FastAPI(title="Scraping API")


class TextInput(BaseModel):
    text: str


# =============================
# CONFIGURATION
# =============================

# ---------- Kijiji ----------

URLKIJII = "https://www.kijiji.ca/b-cars-trucks/sudbury/c174l1700245"

PARAMSKIJII = {
    "address": "Spanish, ON",
    "for-sale-by": "ownr",
    "ll": "46.1947959,-82.3422779",
    "price": "0__",
    "radius": "988.0",
    "view": "list",
}

HEADERSKIJII = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

COOKIESKIJII = {
    "kjses": "a3ada55c-3dda-4d3b-a2f1-5a2dc3e6d11e",
}

# ---------- AutoTrader ----------

URL = "https://www.autotrader.ca/lst"

PARAMS = {
    "atype": "C",
    "custtype": "P",
    "cy": "CA",
    "damaged_listing": "exclude",
    "desc": "1",
    "lat": "46.20007",
    "lon": "-82.34984",
    "offer": "U",
    "size": "40",
    "sort": "age",
    "ustate": "N,U",
    "zip": "Spanish, ON",
    "zipr": "1000",
}

HEADERS = {
    "Host": "www.autotrader.ca",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not_A Brand";v="99", "Chromium";v="142"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Priority": "u=0, i",
}

COOKIES = {
    "as24Visitor": "c3c760d9-0878-408d-a19b-2180d1931375",
}

# ---------- Swoopa ----------

SWOOPA_ACCOUNTS = {
    "primary": {
        "url": "https://backend.getswoopa.com/api/marketplace/",
        "detail_url_template": "https://backend.getswoopa.com/api/marketplace/{id}/",
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0Njc3NjM3LCJpYXQiOjE3NzQ1OTEyMzcsImp0aSI6IjIyNmRmMWQ5ZDIyNzRlMGRhOTUwODBiNGRmMDk4MzA5IiwidXNlcl9pZCI6Ijk1MjE2In0.LqnGNBAoVAZLzPYGeWgrqF-ZyW5LanJ-Isa780898uM",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://app.getswoopa.com",
            "Referer": "https://app.getswoopa.com/",
            "User-Agent": "Mozilla/5.0",
        },
    },
    "secondary": {
        "url": "https://backend.getswoopa.com/api/marketplace/",
        "detail_url_template": "https://backend.getswoopa.com/api/marketplace/{id}/",
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc0Njk1MDQwLCJpYXQiOjE3NzQ2MDg2NDAsImp0aSI6IjA2MmMzYzIwNWFjNjQxMTNhOWIwYjg0NTk3MGVjMTNhIiwidXNlcl9pZCI6Ijk3OTE3In0.mL0wY9XqfsGa80gpw50I-zkRx3ImJBFhrGUav1qCY7w",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://app.getswoopa.com",
            "Referer": "https://app.getswoopa.com/",
            "User-Agent": "Mozilla/5.0",
        },
    },
}


# =============================
# HELPERS
# =============================

def clean_html_description(text: str) -> str:
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_plain_text(text: str) -> str:
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_kijiji_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(
            date_str, "%Y-%m-%dT%H:%M:%S.%fZ"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.strptime(
            date_str, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)


def fetch_swoopa_listing_info(listing_id: str, account_config: dict) -> dict | None:
    detail_template = account_config.get("detail_url_template")
    if not detail_template:
        print("No detail_url_template in config")
        return None

    detail_url = detail_template.format(id=listing_id)

    try:
        resp = requests.get(detail_url, headers=account_config["headers"], timeout=15)
        if resp.status_code != 200:
            print(f"Swoopa detail failed {listing_id}: {resp.status_code}")
            return None
        return resp.json()
    except requests.RequestException as e:
        print("Swoopa detail error:", e)
        return None


def find_autos_listings(obj, results=None):
    if results is None:
        results = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("AutosListing:"):
                results[k] = v
            else:
                find_autos_listings(v, results)

    elif isinstance(obj, list):
        for item in obj:
            find_autos_listings(item, results)

    return results


def add_cookies_to_context(context, cookies_dict: dict, domain: str):
    cookies_to_add = []
    for name, value in cookies_dict.items():
        if value:
            cookies_to_add.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                }
            )
    if cookies_to_add:
        context.add_cookies(cookies_to_add)


def build_autotrader_detail_url(listing_url: str) -> str:
    if not listing_url:
        return ""
    if listing_url.startswith("/"):
        return f"https://www.autotrader.ca{listing_url}"
    return listing_url


def build_kijiji_detail_url(listing_url: str) -> str:
    if not listing_url:
        return ""
    if listing_url.startswith("/"):
        return f"https://www.kijiji.ca{listing_url}"
    return listing_url


def fetch_autotrader_full_description_playwright(page, listing_url: str) -> str:
    """
    يدخل صفحة الإعلان ثم يقرأ seller notes بالكامل.
    """
    detail_url = build_autotrader_detail_url(listing_url)
    if not detail_url:
        return ""

    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        expand_selectors = [
            "#sellerNotesSection button[aria-label*='See more']",
            "#sellerNotesSection button[aria-label*='Voir plus']",
            "#sellerNotesSection button:has-text('See more')",
            "#sellerNotesSection button:has-text('Voir plus')",
            "button[aria-label*='See more']",
            "button[aria-label*='Voir plus']",
            "button:has-text('See more')",
            "button:has-text('Voir plus')",
        ]

        for selector in expand_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1200)
                    break
            except Exception:
                pass

        text = page.evaluate(
            """
            () => {
                const clean = (s) => {
                    if (!s) return "";
                    return s
                        .replace(/\\u00A0/g, " ")
                        .replace(/\\r/g, "")
                        .replace(/[ \\t]+\\n/g, "\\n")
                        .replace(/\\n{3,}/g, "\\n\\n")
                        .trim();
                };

                const seller = document.querySelector(
                    '#sellerNotesSection div[class*="SellerNotesSection_content__"], div[class*="SellerNotesSection_content__"]'
                );

                if (seller) {
                    const raw = seller.textContent || seller.innerText || "";
                    const out = clean(raw);
                    if (out) return out;
                }

                const all = Array.from(document.querySelectorAll("body *"));
                const label = all.find(el =>
                    /^(Vehicle Description|Description du véhicule)$/i.test(
                        (el.textContent || "").trim()
                    )
                );

                if (label) {
                    let node = label;
                    for (let i = 0; i < 7 && node; i++, node = node.parentElement) {
                        const raw = node.innerText || node.textContent || "";
                        const txt = clean(raw);

                        if (!txt) continue;

                        if (
                            /Vehicle Description|Description du véhicule/i.test(txt) &&
                            txt.length > 40
                        ) {
                            let lines = txt
                                .split("\\n")
                                .map(x => x.trim())
                                .filter(Boolean);

                            lines = lines.filter(x =>
                                !/^(Vehicle Description|Description du véhicule|See more|See less|Voir plus|Voir moins)$/i.test(x)
                            );

                            return clean(lines.join("\\n"));
                        }
                    }
                }

                return "";
            }
            """
        )

        text = normalize_plain_text(text)
        if len(text) < 30:
            return ""
        return text

    except Exception as e:
        print(f"[AUTOTRADER DESCRIPTION ERROR] {detail_url} -> {e}")
        return ""


def extract_longest_description_from_obj(obj) -> str:
    best = ""

    def walk(x):
        nonlocal best

        if isinstance(x, dict):
            for k, v in x.items():
                key = str(k).lower()

                if isinstance(v, str) and any(word in key for word in [
                    "description",
                    "body",
                    "adcopy",
                    "sellerdescription",
                    "seller_description",
                    "comments",
                    "content",
                    "text",
                ]):
                    cleaned = normalize_plain_text(v)
                    if len(cleaned) > len(best):
                        best = cleaned

                walk(v)

        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return best.strip()


def fetch_kijiji_full_description_playwright(page, listing_url: str) -> str:
    """
    يدخل صفحة إعلان Kijiji ويحاول استخراج الوصف الكامل من:
    1) JSON-LD / scripts
    2) عناصر DOM التي تحتوي الوصف
    3) section حول عنوان Description
    """
    detail_url = build_kijiji_detail_url(listing_url)
    if not detail_url:
        return ""

    try:
        page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        expand_selectors = [
            "button:has-text('See more')",
            "button:has-text('Read more')",
            "button:has-text('Show more')",
            "button:has-text('Voir plus')",
            "[role='button']:has-text('See more')",
            "[role='button']:has-text('Read more')",
            "[role='button']:has-text('Voir plus')",
        ]

        for selector in expand_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1200)
                    break
            except Exception:
                pass

        text = page.evaluate(
            """
            () => {
                const clean = (s) => {
                    if (!s) return "";
                    return s
                        .replace(/\\u00A0/g, " ")
                        .replace(/\\r/g, "")
                        .replace(/[ \\t]+\\n/g, "\\n")
                        .replace(/\\n{3,}/g, "\\n\\n")
                        .trim();
                };

                const parseJsonSafely = (txt) => {
                    try { return JSON.parse(txt); } catch { return null; }
                };

                const extractLongestDescription = (obj) => {
                    let best = "";

                    const walk = (x) => {
                        if (!x) return;

                        if (Array.isArray(x)) {
                            for (const item of x) walk(item);
                            return;
                        }

                        if (typeof x === "object") {
                            for (const [k, v] of Object.entries(x)) {
                                const key = String(k).toLowerCase();

                                if (
                                    typeof v === "string" &&
                                    /(description|body|adcopy|sellerdescription|seller_description|comments|content|text)/i.test(key)
                                ) {
                                    const c = clean(v);
                                    if (c.length > best.length) best = c;
                                }

                                walk(v);
                            }
                        }
                    };

                    walk(obj);
                    return best.trim();
                };

                // 1) JSON-LD / scripts
                const scriptNodes = Array.from(document.querySelectorAll(
                    'script[type="application/ld+json"], script[type="application/json"]'
                ));

                let bestScriptDesc = "";

                for (const node of scriptNodes) {
                    const raw = (node.textContent || "").trim();
                    if (!raw) continue;

                    const parsed = parseJsonSafely(raw);
                    if (!parsed) continue;

                    const found = extractLongestDescription(parsed);
                    if (found.length > bestScriptDesc.length) {
                        bestScriptDesc = found;
                    }
                }

                if (bestScriptDesc.length > 40) return bestScriptDesc;

                // 2) عناصر مباشرة مرشحة للوصف
                const selectors = [
                    '[data-testid*="description"]',
                    '[class*="description"]',
                    '[id*="description"]',
                    'section [class*="description"]',
                    'section [data-testid*="description"]',
                    'div [class*="description"]',
                ];

                let bestDomDesc = "";

                for (const selector of selectors) {
                    const nodes = Array.from(document.querySelectorAll(selector));
                    for (const node of nodes) {
                        const txt = clean(node.innerText || node.textContent || "");
                        if (!txt) continue;

                        // تجاهل النصوص القصيرة أو العناوين فقط
                        if (txt.length < 40) continue;
                        if (/^(description|description du véhicule)$/i.test(txt)) continue;

                        if (txt.length > bestDomDesc.length) {
                            bestDomDesc = txt;
                        }
                    }
                }

                if (bestDomDesc.length > 40) return bestDomDesc;

                // 3) ابحث عن عنوان Description وخذ أقرب container غني بالنص
                const all = Array.from(document.querySelectorAll("body *"));
                const label = all.find(el =>
                    /^(description|item description|description du véhicule)$/i.test(
                        (el.textContent || "").trim()
                    )
                );

                if (label) {
                    let node = label;
                    for (let i = 0; i < 8 && node; i++, node = node.parentElement) {
                        const raw = clean(node.innerText || node.textContent || "");
                        if (!raw || raw.length < 40) continue;

                        let lines = raw
                            .split("\\n")
                            .map(x => x.trim())
                            .filter(Boolean);

                        lines = lines.filter(x =>
                            !/^(description|item description|description du véhicule|see more|read more|show more|voir plus)$/i.test(x)
                        );

                        const finalText = clean(lines.join("\\n"));
                        if (finalText.length > 40) return finalText;
                    }
                }

                return "";
            }
            """
        )

        text = normalize_plain_text(text)
        if len(text) < 30:
            return ""
        return text

    except Exception as e:
        print(f"[KIJIJI DESCRIPTION ERROR] {detail_url} -> {e}")
        return ""


def fetch_swoopa_marketplace(account: str, pages: int, with_description: bool):
    if account not in SWOOPA_ACCOUNTS:
        raise HTTPException(status_code=400, detail="Invalid Swoopa account")

    swoopa = SWOOPA_ACCOUNTS[account]
    url = swoopa["url"]
    headers = swoopa["headers"]

    all_results = []

    for _ in range(pages):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            raise HTTPException(
                status_code=502,
                detail=f"Swoopa {account} request failed: {str(e)}",
            )

        try:
            data = r.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail=f"Swoopa {account} returned non-JSON response",
            )

        all_results.extend(data.get("results", []))

        url = data.get("next")
        if not url:
            break

        time.sleep(1)

    if with_description:
        enriched = []
        for item in all_results:
            listing_id = item.get("id")
            desc = None

            if listing_id:
                info_data = fetch_swoopa_listing_info(listing_id, swoopa)
                if info_data:
                    desc = info_data.get("listing_description")

            item["listing_description"] = desc
            enriched.append(item)

        all_results = enriched

    return {
        "count": len(all_results),
        "results": all_results,
    }


# =============================
# ENDPOINTS
# =============================

def build_autotrader_detail_url(listing_url: str) -> str:
    if not listing_url:
        return ""
    if listing_url.startswith("/"):
        return f"https://www.autotrader.ca{listing_url}"
    return listing_url


def normalize_plain_text(text: str) -> str:
    if not text:
        return ""
    text = html_lib.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def add_autotrader_cookies_to_context(context):
    cookies_to_add = []

    for name, value in COOKIES.items():
        if value:
            cookies_to_add.append(
                {
                    "name": name,
                    "value": value,
                    "domain": ".autotrader.ca",
                    "path": "/",
                    "secure": True,
                }
            )

    if cookies_to_add:
        context.add_cookies(cookies_to_add)


def extract_autotrader_description_from_body(body_text: str) -> str:
    body_text = normalize_plain_text(body_text)

    patterns = [
        r"Vehicle Description\s*(.+?)(?:How do you like the site\?|Car insurance|Verified History Report|Seller|Report listing|Disclaimer:|Back to top)",
        r"Description du véhicule\s*(.+?)(?:Comment aimez-vous le site|Assurance automobile|Rapport d'historique|Vendeur|Signaler l'annonce|Avis de non-responsabilité|Retour en haut)",
    ]

    for pattern in patterns:
        m = re.search(pattern, body_text, re.DOTALL | re.IGNORECASE)
        if m:
            desc = normalize_plain_text(m.group(1))
            if len(desc) > 40:
                return desc

    return ""


def fetch_autotrader_full_description_playwright(page, listing_url: str) -> str:
    detail_url = build_autotrader_detail_url(listing_url)
    if not detail_url:
        return ""

    try:
        page.goto(detail_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        # لو فيه See more جوه seller notes
        expand_selectors = [
            "#sellerNotesSection button[aria-label*='See more']",
            "#sellerNotesSection button[aria-label*='Voir plus']",
            "#sellerNotesSection button:has-text('See more')",
            "#sellerNotesSection button:has-text('Voir plus')",
            "button[aria-label*='See more']",
            "button[aria-label*='Voir plus']",
            "button:has-text('See more')",
            "button:has-text('Voir plus')",
        ]

        for selector in expand_selectors:
            try:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    btn.click(timeout=3000)
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # 1) جرّب العنصر الحقيقي للوصف
        try:
            content = page.locator(
                "#sellerNotesSection div[class*='SellerNotesSection_content__'], div[class*='SellerNotesSection_content__']"
            ).first

            if content.count() > 0:
                txt = normalize_plain_text(content.inner_text(timeout=5000))
                if len(txt) > 40:
                    return txt
        except Exception:
            pass

        # 2) fallback قوي: استخرج الوصف من body text بين headings
        body_text = page.locator("body").inner_text(timeout=10000)
        desc = extract_autotrader_description_from_body(body_text)
        if desc:
            return desc

        return ""

    except Exception as e:
        print(f"[AUTOTRADER DESCRIPTION ERROR] {detail_url} -> {e}")
        return ""


@app.get("/")
def read_root():
    return {
        "message": "Scraping API",
        "endpoints": {
            "/scrape_autotrader": "GET - Scrape Autotrader listings",
            "/scrape_kijiji": "GET - Scrape Kijiji listings",
            "/fetch-marketplace-primary": "GET - Scrape primary marketplace listings",
            "/fetch-marketplace-secondary": "GET - Scrape secondary marketplace listings",
            "/health": "GET - Health check",
        },
    }


@app.get("/scrape_autotrader")
def scrape_autotrader():
    """
    Scrape Autotrader listings and return structured data.
    يدخل صفحة الإعلان أولًا ويحسب description من صفحة العربية نفسها.
    """
    try:
        response = requests.get(
            URL,
            params=PARAMS,
            headers=HEADERS,
            cookies=COOKIES,
            verify=False,
            timeout=30,
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Request failed with status code: {response.status_code}",
            )

        html = response.text

        match = re.search(
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )

        if not match:
            raise HTTPException(
                status_code=500,
                detail="Embedded JSON not found in response",
            )

        json_text = match.group(1).replace("&quot;", '"')
        data = json.loads(json_text)

        page_props = data["props"]["pageProps"]
        number_of_results = page_props["numberOfResults"]
        cars = page_props["listings"]

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                ignore_https_errors=True,
                locale="en-CA",
            )

            add_autotrader_cookies_to_context(context)

            page = context.new_page()
            page.set_default_timeout(20000)

            for car in cars:
                vehicle = car.get("vehicle", {})
                price_data = car.get("price", {})
                location = car.get("location", {})

                make = vehicle.get("make", "")
                model = vehicle.get("model", "")
                year = vehicle.get("modelYear", "")
                mileage = vehicle.get("mileageInKm")

                price = price_data.get("priceFormatted", "")
                city = location.get("city", "")
                url = car.get("url", "")
                image = car["images"][0] if car.get("images") else None

                # الوصف من صفحة العربية نفسها
                description = fetch_autotrader_full_description_playwright(page, url)
                description_source = "detail_page_playwright"

                # fallback اختياري فقط لو فشل
                if not description:
                    raw_description = car.get("description", "") or ""
                    description = clean_html_description(raw_description)
                    description_source = "search_results_snippet"

                title = f"{year} {make} {model}".strip()

                print("=" * 80)
                print("TITLE:", title)
                print("URL:", url)
                print("DESC_SOURCE:", description_source)
                print("DESC_LEN:", len(description))
                print("DESC_PREVIEW:", repr(description[:400]))

                car_data = {
                    "title": title,
                    "price": price,
                    "city": city,
                    "mileage_km": mileage,
                    "image": image,
                    "url": url,
                    "description": description,
                    "description_source": description_source,
                    "make": make,
                    "model": model,
                    "year": year,
                }

                results.append(car_data)

            context.close()
            browser.close()

        return {
            "success": True,
            "total_results": number_of_results,
            "scraped_count": len(results),
            "source": "AutoTrader",
            "cars": results,
        }

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timeout")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"JSON parsing error: {str(e)}",
        )
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing expected data field: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}",
        )


@app.get("/scrape_kijiji")
def scrape_kijiji():
    """
    يدخل صفحة كل إعلان Kijiji أولًا، يسحب الوصف الكامل،
    وبعدها فقط يبني car_data.
    """
    try:
        r = requests.get(
            URLKIJII,
            params=PARAMSKIJII,
            headers=HEADERSKIJII,
            cookies=COOKIESKIJII,
            timeout=30,
        )

        if r.status_code != 200:
            raise HTTPException(status_code=500, detail="Request failed")

        match = re.search(
            r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
            r.text,
            re.DOTALL,
        )

        if not match:
            raise HTTPException(status_code=500, detail="Embedded JSON not found")

        raw_json = (
            match.group(1)
            .replace("&quot;", '"')
            .replace("&amp;", "&")
            .strip()
        )

        data = json.loads(raw_json)
        listings_map = find_autos_listings(data)
        now = datetime.now(timezone.utc)

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERSKIJII["User-Agent"],
                ignore_https_errors=True,
                locale="en-CA",
            )
            add_cookies_to_context(context, COOKIESKIJII, ".kijiji.ca")

            page = context.new_page()
            page.set_default_timeout(20000)

            for listing in listings_map.values():
                attributes = listing.get("attributes", {}).get("all", [])

                def get_attr(name):
                    for a in attributes:
                        if a.get("canonicalName") == name:
                            vals = a.get("canonicalValues")
                            return vals[0] if vals else None
                    return None

                activation = parse_kijiji_date(listing.get("activationDate"))
                sorting = parse_kijiji_date(listing.get("sortingDate"))
                amount = listing.get("price", {}).get("amount")

                if isinstance(amount, (int, float)):
                    price = amount // 100
                else:
                    price = amount

                listing_url = listing.get("url", "")
                description = fetch_kijiji_full_description_playwright(page, listing_url)
                description_source = "detail_page_playwright"

                if not description:
                    description = clean_html_description(listing.get("description") or "")
                    description_source = "listing_json_snippet"

                results.append(
                    {
                        "title": listing.get("title"),
                        "description": description,
                        "description_source": description_source,
                        "price": price,
                        "currency": "CAD",
                        "url": listing_url,
                        "images": listing.get("imageUrls") or [],
                        "brand": get_attr("carmake"),
                        "model": get_attr("carmodel"),
                        "year": get_attr("caryear"),
                        "mileage_km": get_attr("carmileageinkms"),
                        "body_type": get_attr("carbodytype"),
                        "color": get_attr("carcolor"),
                        "doors": get_attr("noofdoors"),
                        "fuel_type": get_attr("carfueltype"),
                        "transmission": get_attr("cartransmission"),
                        "activation_date": activation.isoformat() if activation else None,
                        "sorting_date": sorting.isoformat() if sorting else None,
                        "time_since_activation": str(now - activation) if activation else None,
                    }
                )

            context.close()
            browser.close()

        results.sort(key=lambda x: x["sorting_date"] or "", reverse=True)

        return {
            "count": len(results),
            "cars": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kijiji error: {str(e)}")


@app.get("/fetch-marketplace-primary")
def fetch_marketplace_primary(
    pages: int = Query(1, ge=1, le=100),
    account: str = Query("primary"),
    with_description: bool = True,
):
    return fetch_swoopa_marketplace(
        account=account,
        pages=pages,
        with_description=with_description,
    )


@app.get("/fetch-marketplace-secondary")
def fetch_marketplace_secondary(
    pages: int = Query(1, ge=1, le=100),
    account: str = Query("secondary"),
    with_description: bool = True,
):
    return fetch_swoopa_marketplace(
        account=account,
        pages=pages,
        with_description=with_description,
    )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "autotrader_scraper"}
