"""
Cineco public endpoints:
- https://www.cinecolombia.com/api/movies
- https://www.cinecolombia.com/api/theaters
"""
import datetime as dt
import json
from itertools import groupby
from typing import ClassVar, Self

import boto3
from pydantic import BaseModel

from scrape_cineco import settings

from ._utils import (
    JSON_KWARGS,
    get_soup,
    send_telegram_message,
    spanish_month_to_number,
)


class CinecoMovie(BaseModel):
    title: str
    url: str
    premiere_date: dt.date
    status: str
    genres: list[str]


class Cineco(BaseModel):
    base_url: ClassVar[str] = "https://www.cinecolombia.com"
    movies: list[CinecoMovie]

    def save_json(self, filename: str = "cineco_movies.json") -> None:
        with open(f"{settings.local_tmp_dir}/{filename}", "w") as f:
            json.dump(self.movies, f, **JSON_KWARGS)

    def upload_as_json_to_s3(self, bucket: str, obj_key: str):
        s3 = boto3.client("s3")
        s3.put_object(
            Body=json.dumps(self.movies, **JSON_KWARGS), Bucket=bucket, Key=obj_key
        )

    @classmethod
    def parse_movie_grid_html(cls, urlpath: str) -> list[CinecoMovie]:
        soup = get_soup(f"{cls.base_url}/bogota/{urlpath}")
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

            status = urlpath
            # find if it's premiere
            badge = movie.find("span", class_="movie-item__badge")
            if badge and badge.text == "Estreno":
                status = "premiere"

            movies.append(
                CinecoMovie(
                    title=movie.h2.text,
                    url=f"{cls.base_url}{movie.attrs["href"]}",
                    premiere_date=premiere_date,
                    status=status,
                    genres=genres,
                )
            )
        return sorted(movies, key=lambda movie: movie.premiere_date)

    @classmethod
    def scrape_current(cls) -> Self:
        movies = []
        for p in ["cartelera", "pronto"]:
            movies.extend(cls.parse_movie_grid_html(p))
        return cls(movies=movies)

    @classmethod
    def from_s3_json(cls, bucket: str, obj_key: str) -> Self:
        s3 = boto3.client("s3")
        json_str = s3.get_object(Bucket=bucket, Key=obj_key)["Body"].read().decode()
        return cls(movies=json.loads(json_str))

    @classmethod
    def from_s3_snapshot(cls, bucket: str, date: str) -> Self:
        s3 = boto3.client("s3")
        possible_objs = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=f"cineco/movies/{date}",
        )
        # Uses the first object found for that date
        obj = possible_objs["Contents"][0]
        return cls.from_s3_json(bucket, obj["Key"])


def build_compare_message(newer_cineco: Cineco, older_cineco: Cineco):
    message = "*Pelis Cineco*\n\n"
    message += "*Cartelera*\n"
    pronto = []
    cartelera = []
    # A movie is in cartelera if its status is not "pronto" (i.e. "premiere" or
    # "cartelera").
    for m in newer_cineco.movies:
        if m.status == "pronto":
            pronto.append(m)
        else:
            cartelera.append(m)
    older_cartelera_titles = [
        m.title for m in older_cineco.movies if m.status != "pronto"
    ]
    # A cartelera movie was removed if it's not in the new cartelera.
    cartelera_removed = [
        mt for mt in older_cartelera_titles if mt not in [n.title for n in cartelera]
    ]
    for movie in sorted(cartelera, key=lambda m: m.premiere_date, reverse=True):
        movie_message = "🍿" if movie.status == "premiere" else "📽️"
        if movie.title not in older_cartelera_titles:
            # The movie was added
            movie_message += "🆕"
        movie_message += f" [{movie.title}]({movie.url})\n"
        message += movie_message
    for movie_title in cartelera_removed:
        message += f"👋 {movie_title}\n"

    older_pronto_titles = [m.title for m in older_cineco.movies if m.status == "pronto"]
    pronto_removed = [
        mt
        for mt in older_pronto_titles
        if mt not in [n.title for n in newer_cineco.movies]
    ]
    if pronto or pronto_removed:
        pronto_by_release_date = {
            k: list(g) for k, g in groupby(pronto, key=lambda m: m.premiere_date)
        }
        pronto_by_release_date = dict(sorted(pronto_by_release_date.items()))
        message += "\n*Pronto*\n"
        for release_date, movies in pronto_by_release_date.items():
            message += f"{release_date.strftime("%Y/%m/%d")}\n"
            for movie in movies:
                movie_message = "🛬" if movie.title in older_pronto_titles else "🛬🆕"
                movie_message += f"[{movie.title}]({movie.url})\n"
                message += movie_message
        for movie in pronto_removed:
            message += f"👋 {movie.title}\n"

    return message


def main():
    current_movies = Cineco.scrape_current()
    colombia_tz = dt.timezone(dt.timedelta(hours=-5))
    datetime_col = dt.datetime.now(colombia_tz)
    current_movies.upload_as_json_to_s3(
        settings.bucket.get_secret_value(), f"cineco/movies/{datetime_col}.json"
    )

    yesterday_date = (datetime_col - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    ytd_movies = Cineco.from_s3_snapshot(
        settings.bucket.get_secret_value(), yesterday_date
    )

    msg = build_compare_message(newer_cineco=current_movies, older_cineco=ytd_movies)
    send_telegram_message(msg)


if __name__ == "__main__":
    main()