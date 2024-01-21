import datetime as dt
import json

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from scrape_cineco import settings

from ._utils import AWS_SESSION, spanish_month_to_number

CINECO_URL = "https://www.cinecolombia.com"


# Models


class CarteleraMovie(BaseModel):
    title: str
    url: str
    premiere_date: dt.date
    is_premiere: bool


# Cineco API endpoints


def save_api_movies():
    r = httpx.get(f"{CINECO_URL}/api/movies")
    data = r.json()
    with open(f"{settings.local_tmp_dir}/cineco_api_movies.json", "w") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def save_api_theaters():
    r = httpx.get(f"{CINECO_URL}/api/theaters")
    data = r.json()
    with open(f"{settings.local_tmp_dir}/cineco_api_theaters.json", "w") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# /cartelera


def get_cartelera_soup() -> str:
    cartelera_url = f"{CINECO_URL}/bogota/cartelera"
    r = httpx.get(cartelera_url)
    return BeautifulSoup(r.text, "lxml")


def save_cartelera_html() -> None:
    with open(f"{settings.local_tmp_dir}/cartelera.html", "w") as f:
        f.write(get_cartelera_soup().prettify())


def parse_cartelera() -> list[CarteleraMovie]:
    soup = get_cartelera_soup()

    movies = []
    for movie in soup.find_all("a", class_="movie-item"):
        premiere_date = None
        for movie_meta in movie.find_all("span", class_="movie-item__meta"):
            # Extract premiere_date
            text = movie_meta.text
            if "Estreno:" in text:
                date = text.replace("Estreno:", "").strip().lower().split("-")
                date[1] = spanish_month_to_number(date[1])
                premiere_date = "-".join(reversed(date))

        is_premiere = False
        if movie.find("span", class_="movie-item__badge"):
            is_premiere = True

        movies.append(
            CarteleraMovie(
                title=movie.h2.text,
                url=f"{CINECO_URL}{movie.attrs["href"]}",
                premiere_date=premiere_date,
                is_premiere=is_premiere,
            )
        )
    return sorted(movies, key=lambda movie: movie.premiere_date)


def upload_cartelera_to_s3():
    cartelera = parse_cartelera()
    s3 = AWS_SESSION.client("s3")
    colombia_tz = dt.timezone(dt.timedelta(hours=-5))
    datetime_col = dt.datetime.now(colombia_tz)
    # TODO: Save metadata
    s3.put_object(
        Body=json.dumps(
            [movie.model_dump(mode="json") for movie in cartelera], indent=4
        ),
        Bucket=settings.bucket_name.get_secret_value(),
        Key=f"cartelera/{datetime_col}.json",
    )


def main():
    upload_cartelera_to_s3()


if __name__ == "__main__":
    main()
