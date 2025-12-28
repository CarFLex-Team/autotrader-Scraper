from fastapi import FastAPI, HTTPException
import requests

app = FastAPI(title="ScrapingBee Proxy API")

SCRAPINGBEE_API_KEY = "4Z7NQS4HD6KZ37X8R46ACMJLZ0JG2INPMVNVSTRZJ9RUK5EE305BFU9XX1FFUGIEBY1UG7PIIQE3GA54"
TARGET_URL = "https://backend.getswoopa.com/api/marketplace/"
AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY3MDI2MjQ3LCJpYXQiOjE3NjY5Mzk4NDcsImp0aSI6ImE5ZWJkYjQ0ZWE4ZTQ1ZjRiMjYwYTgzNGZkNmIzYTZmIiwidXNlcl9pZCI6Ijk1MjE2In0.Honc2MdInU8C23IHUHobq5GWf_xQPVxWvlL4JaewMR4"

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1"


@app.get("/")
def health():
    return {"status": "running"}


@app.get("/fetch-marketplace")
def fetch_marketplace():
    try:
        response = requests.get(
            url=SCRAPINGBEE_ENDPOINT,
            params={
                "api_key": SCRAPINGBEE_API_KEY,
                "url": TARGET_URL,
                "premium_proxy": "true",
                "country_code": "ca",
                "forward_headers": "true"
            },
            headers={
                "spb-accept": "application/json",
                "spb-authorization": f"Bearer {AUTH_TOKEN}"
            },
            timeout=30
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )

        return response.json()

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))





