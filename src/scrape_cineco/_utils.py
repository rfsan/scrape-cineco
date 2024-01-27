import httpx
from bs4 import BeautifulSoup

from scrape_cineco import settings


def spanish_month_to_number(month: str) -> str:
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


def get_soup(url: str) -> str:
    r = httpx.get(url)
    return BeautifulSoup(r.text, "lxml")


def save_html(url: str, filename: str) -> None:
    with open(f"{settings.local_tmp_dir}/{filename}.html", "w") as f:
        f.write(get_soup(url).prettify())
