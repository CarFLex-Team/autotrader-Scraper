# from fastapi import FastAPI
# import requests

# app = FastAPI(title="Autotrader Scraping API")

# URL = "https://www.autotrader.ca/lst"

# PARAMS = {
#     "atype": "C",
#     "custtype": "P",
#     "cy": "CA",
#     "desc": 1,
#     "lat": "42.98014450073242",
#     "lon": "-81.23054504394531",
#     "offer": "N",
#     "size": "40",
#     "sort": "age",
#     "zip": "N6B3B4 London, ON",
#     "zipr": "1000"
# }

# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# }

# @app.get("/")
# def health_check():
#     return {"status": "ok"}

# @app.get("/scrape_autotrader")
# def scrape_autotrader():

#     r = requests.get(
#         URL,
#         params=PARAMS,
#         headers=HEADERS,
#         timeout=30
#     )

#     if r.status_code != 200:
#         raise HTTPException(500, "Request failed")

#     match = re.search(
#         r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
#         r.text,
#         re.DOTALL
#     )

#     if not match:
#         raise HTTPException(500, "JSON not found")

#     data = json.loads(match.group(1).replace("&quot;", '"'))
#     listings = data["props"]["pageProps"]["listings"]

#     results = []

#     for car in listings:
#         v = car.get("vehicle", {})
#         p = car.get("price", {})
#         l = car.get("location", {})

#         images = car.get("images") or []
#         image = images[0] if images else None

#         results.append({
#             "title": f"{v.get('modelYear','')} {v.get('make','')} {v.get('model','')}",
#             "price": p.get("priceFormatted"),
#             "mileage_km": v.get("mileageInKm"),
#             "city": l.get("city"),
#             "image": image,
#             "url": car.get("url")
#         })

#     return {
#         "count": len(results),
#         "cars": results
#     }




from fastapi import FastAPI, HTTPException
import requests
import json
import re
from datetime import datetime, timezone

app = FastAPI(title="Kijiji Cars Scraper API")

URL = "https://www.kijiji.ca/b-cars-trucks/sudbury/c174l1700245"

PARAMS = {
    "address": "Spanish, ON",
    "for-sale-by": "ownr",
    "ll": "46.1947959,-82.3422779",
    "price": "0__",
    "radius": "988.0",
    "view": "list",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html",
}

COOKIES = {
    "kjses": "a3ada55c-3dda-4d3b-a2f1-5a2dc3e6d11e",
}

# =============================
# HELPERS
# =============================
def find_autos_listings(obj, results=None):
    if results is None:
        results = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("AutosListing:"):
                results[k] = v
            else:
                find_autos_listings(v, results)

    elif isinstance(obj, list):
        for item in obj:
            find_autos_listings(item, results)

    return results


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


# =============================
# API ENDPOINT
# =============================
@app.get("/")
def scrape_kijiji():

    r = requests.get(
        URL,
        params=PARAMS,
        headers=HEADERS,
        cookies=COOKIES,
        timeout=30,
    )

    if r.status_code != 200:
        raise HTTPException(500, "Request failed")

    match = re.search(
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
        r.text,
        re.DOTALL,
    )


    if not match:
        print(r.text[:2000])  # see what Vercel receives
        raise HTTPException(500, "Embedded JSON not found")


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

        results.append({
            "title": listing.get("title"),
            "description": listing.get("description"),
            "price": listing.get("price", {}).get("amount"),
            "currency": "CAD",
            "url": listing.get("url"),
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
            "time_since_activation": (
                str(now - activation) if activation else None
            ),
        })

    results.sort(
        key=lambda x: x["sorting_date"] or "",
        reverse=True,
    )

    return {
        "count": len(results),
        "cars": results,
    }