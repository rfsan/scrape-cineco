import httpx
from pydantic.json import pydantic_encoder

from scrape_cineco import settings

JSON_KWARGS = dict(ensure_ascii=False, indent=2, default=pydantic_encoder)
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",  # noqa: E501
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.6",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",  # noqa: E501
    "Referer": "https://www.google.com/",
}


def spanish_month_to_number(month: str) -> str:
    month = month.lower()[:3]
    return {
        "ene": "01",
        "feb": "02",
        "mar": "03",
        "abr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "ago": "08",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dic": "12",
    }[month]


def ntfy_notification():
    r = httpx.post(
        f"https://ntfy.sh/{settings.ntfy_topic.get_secret_value()}",
        data="Actualizadas las películas de Cineco",
        headers={
            "Click": f"https://gist.github.com/rfsan/{settings.gist_id.get_secret_value()}"
        },
    )
    r.raise_for_status()
