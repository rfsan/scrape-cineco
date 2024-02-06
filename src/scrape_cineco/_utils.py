import httpx
from bs4 import BeautifulSoup
from pydantic.json import pydantic_encoder

from scrape_cineco import settings

JSON_KWARGS = dict(ensure_ascii=False, indent=2, default=pydantic_encoder)


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


def send_telegram_message(message: str):
    r = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_token.get_secret_value()}/sendMessage",
        json={
            "chat_id": 6944099368,
            "text": message,
            "parse_mode": "MarkdownV2",
        },
    )
    r.raise_for_status()


def get_telegram_updates():
    r = httpx.get(
        f"https://api.telegram.org/bot{settings.telegram_token.get_secret_value()}/getUpdates"
    )
    r.raise_for_status()
    for update in r.json()["result"]:
        chat = update["message"]["chat"]
        print(chat["first_name"], chat["id"])


if __name__ == "__main__":
    get_telegram_updates()
