import datetime as dt
import json

import boto3
import httpx
from pydantic import BaseModel

from scrape_cineco import settings

from ._utils import get_soup, spanish_month_to_number

CINECO_URL = "https://www.cinecolombia.com"


class CinecoMovie(BaseModel):
    title: str
    url: str
    premiere_date: dt.date
    status: str
    genres: list[str]


def parse_movie_grid_html(path: str) -> list[CinecoMovie]:
    soup = get_soup(f"{CINECO_URL}/bogota/{path}")

    movies = []
    for movie in soup.find_all("a", class_="movie-item"):
        premiere_date = None
        genres = []
        for movie_meta in movie.find_all("span", class_="movie-item__meta"):
            # Extract premiere_date
            text = movie_meta.text
            if "Estreno:" in text:
                date = text.replace("Estreno:", "").strip().lower().split("-")
                date[1] = spanish_month_to_number(date[1])
                premiere_date = "-".join(reversed(date))
            elif "Género:" in text:
                text = text.replace("Género:", "").strip()
                # remove new lines
                text = " ".join(text.splitlines())
                # replace multiple whitespaces with only one
                text = " ".join(text.split())
                genres = [g.strip() for g in text.split(",")]

        status = path
        # find if it's premiere
        if movie.find("span", class_="movie-item__badge"):
            status = "premiere"

        movies.append(
            CinecoMovie(
                title=movie.h2.text,
                url=f"{CINECO_URL}{movie.attrs["href"]}",
                premiere_date=premiere_date,
                status=status,
                genres=genres,
            )
        )
    return sorted(movies, key=lambda movie: movie.premiere_date)


def cineco_movies() -> list[CinecoMovie]:
    movies = []
    for p in ["cartelera", "pronto"]:
        movies.extend(parse_movie_grid_html(p))
    return movies


def save_cineco_movies_json():
    movies = cineco_movies()
    with open(f"{settings.local_tmp_dir}/cineco_movies.json", "w") as f:
        json.dump(
            [movie.model_dump(mode="json") for movie in movies],
            f,
            indent=4,
            ensure_ascii=False,
        )


def upload_cineco_movies_to_s3():
    movies = cineco_movies()

    s3 = boto3.client("s3")
    colombia_tz = dt.timezone(dt.timedelta(hours=-5))
    datetime_col = dt.datetime.now(colombia_tz)
    s3.put_object(
        Body=json.dumps([movie.model_dump(mode="json") for movie in movies], indent=4),
        Bucket=settings.bucket.get_secret_value(),
        Key=f"cineco/movies/{datetime_col}.json",
    )


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


def main():
    upload_cineco_movies_to_s3()


if __name__ == "__main__":
    main()
