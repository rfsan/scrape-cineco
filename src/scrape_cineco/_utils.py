import boto3

from scrape_cineco import settings

SPANISH_MONTH_TO_NUMBER_MAP = {
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
}


def spanish_month_to_number(month: str) -> str:
    return SPANISH_MONTH_TO_NUMBER_MAP[month]


AWS_SESSION = boto3.Session(
    aws_access_key_id=settings.aws_access_key_id.get_secret_value(),
    aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
)
