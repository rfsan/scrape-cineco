"""
Cineco public endpoints:
- https://www.cinecolombia.com/api/movies
- https://www.cinecolombia.com/api/theaters
"""

import asyncio
import datetime as dt
import json
import subprocess
from enum import Enum
from itertools import groupby
from typing import ClassVar, Self

import boto3
import httpx
from pydantic import BaseModel
from selectolax.parser import HTMLParser

from scrape_cineco import settings

from . import _utils


class MovieStatus(Enum):
    CARTELERA = "cartelera"
    PRONTO = "pronto"


class CinecoMovie(BaseModel):
    title: str
    premiere_date: dt.date
    url: str
    status: MovieStatus
    genres: list[str]
    premiere: bool = False
    presale: bool = False

    def __hash__(self) -> int:
        return hash((self.title, self.premiere_date))

    def __eq__(self, other) -> bool:
        return self.title == other.title and self.premiere_date == other.premiere_date


class CinecoSnapshot(BaseModel):
    movies: list[CinecoMovie]

    def group_by_status(self) -> dict[MovieStatus, list[CinecoMovie]]:
        return {
            status: [m for m in self.movies if m.status == status]
            for status in MovieStatus
        }

    def save_json(self, filename: str = "cineco_movies.json") -> None:
        json_path = settings.tmp_dir / filename
        json_path.write_text(self.movies_json_string())

    def upload_as_json_to_s3(self, bucket: str, obj_key: str):
        s3 = boto3.client("s3")
        s3.put_object(Body=self.movies_json_string(), Bucket=bucket, Key=obj_key)

    def movies_json_string(self) -> str:
        return json.dumps(self.movies, **_utils.JSON_KWARGS)

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

    def __iter__(self):
        return iter(self.movies)


class CinecoScraper:
    base_url: ClassVar[str] = "https://www.cinecolombia.com"

    @staticmethod
    async def scrape(save_html: bool = False) -> CinecoSnapshot:
        async with httpx.AsyncClient(
            headers=_utils.HEADERS, base_url=f"{CinecoScraper.base_url}/bogota"
        ) as client:
            movies = []
            to_do = [client.get(x) for x in ("cartelera", "pronto")]
            for coro in asyncio.as_completed(to_do):
                r = await coro
                r.raise_for_status()
                slug = r.url.path.split("/")[-1]
                if save_html:
                    await CinecoScraper.save_html(r, slug)
                movies.extend(await CinecoScraper.parse_html(r, slug))

            movies = sorted(set(movies), key=lambda movie: movie.premiere_date)
            # Movies with presale appear in both "pronto" and "cartelera" pages.
            return CinecoSnapshot(movies=movies)

    @staticmethod
    async def save_html(r: httpx.Response, slug: str) -> None:
        await asyncio.to_thread(
            lambda: (settings.tmp_dir / f"{slug}.html").write_text(r.text)
        )
        print(f"Saved {slug}.html")

    @staticmethod
    async def parse_html(r: httpx.Response, slug: str) -> list[CinecoMovie]:
        movies = []
        tree = HTMLParser(r.text)
        for movie in tree.css("a.movie-item"):
            premiere_date = None
            genres = []
            status = slug
            premiere = False
            presale = False

            for movie_meta in movie.css("span.movie-item__meta"):
                text = movie_meta.text(strip=True)
                # Extract premiere_date
                if "Estreno:" in text:
                    date = text.replace("Estreno:", "").strip().lower().split("-")
                    date[1] = _utils.spanish_month_to_number(date[1])
                    premiere_date = "-".join(reversed(date))
                # Extract genres
                elif "Género:" in text:
                    text = text.replace("Género:", "").strip()
                    # remove new lines
                    text = " ".join(text.splitlines())
                    # replace multiple whitespaces with only one
                    text = " ".join(text.split())
                    genres = sorted({g.strip() for g in text.split(",")})

            if badge := movie.css_first("span.movie-item__badge"):
                match badge := badge.text(strip=True):
                    case "Estreno":
                        premiere = True
                    case "Preventa":
                        presale = True
                        status = MovieStatus.PRONTO
                    case _:
                        raise ValueError("Unknown badge:", badge)

            movies.append(
                CinecoMovie(
                    title=movie.css_first("h2").text(strip=True),
                    url=CinecoScraper.base_url + movie.attributes["href"],
                    premiere_date=premiere_date,
                    status=status,
                    genres=genres,
                    premiere=premiere,
                    presale=presale,
                )
            )
        if not movies:
            raise ValueError("No movies found in", slug)
        return movies


def build_compare_message(  # noqa: C901
    newer_cineco: CinecoSnapshot, older_cineco: CinecoSnapshot
) -> str:
    message = "# Películas Cineco\n\n"
    message += "## Cartelera\n\n"
    newer_grouped = newer_cineco.group_by_status()
    older_grouped = older_cineco.group_by_status()

    # Movies in Cartelera
    for movie in sorted(
        newer_grouped[MovieStatus.CARTELERA],
        key=lambda m: m.premiere_date,
        reverse=True,
    ):
        movie_message = "- "
        if movie.premiere:
            movie_message += "🍿"
        if movie not in older_grouped[MovieStatus.CARTELERA]:
            # The movie was added
            movie_message += "🆕"
        movie_message += f"[{movie.title}]({movie.url})\n"
        message += movie_message
    # Movies removed from cartelera
    for movie in older_grouped[MovieStatus.CARTELERA]:
        if movie not in newer_grouped[MovieStatus.CARTELERA]:
            message += f"- 👋 {movie.title}\n"

    # Movies in Pronto
    message += "\n## Pronto\n"
    pronto_by_release_date = {
        k: list(g)
        for k, g in groupby(
            sorted(newer_grouped[MovieStatus.PRONTO], key=lambda m: m.premiere_date),
            key=lambda m: m.premiere_date,
        )
    }
    for release_date, movies in pronto_by_release_date.items():
        message += f"\n### {release_date}\n\n"
        for movie in movies:
            movie_message = "- "
            if movie not in older_grouped[MovieStatus.PRONTO]:
                movie_message += "🆕"
            movie_message += f"[{movie.title}]({movie.url})\n"
            message += movie_message
    # Movies removed from Pronto that are not in Cartelera
    for movie in older_grouped[MovieStatus.PRONTO]:
        if movie not in newer_cineco:
            message += f"- 👋 {movie.title}\n"

    return message


def main():
    current_movies = asyncio.run(CinecoScraper.scrape())
    colombia_tz = dt.timezone(dt.timedelta(hours=-5))
    datetime_col = dt.datetime.now(colombia_tz)
    current_movies.upload_as_json_to_s3(
        settings.bucket.get_secret_value(), f"cineco/movies/{datetime_col}.json"
    )

    yesterday_date = (datetime_col - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    ytd_movies = CinecoSnapshot.from_s3_snapshot(
        settings.bucket.get_secret_value(), yesterday_date
    )

    msg = build_compare_message(newer_cineco=current_movies, older_cineco=ytd_movies)
    message_file = settings.tmp_dir / "cine.md"
    message_file.write_text(msg)
    subprocess.run(
        [
            "gh",
            "gist",
            "edit",
            settings.gist_id.get_secret_value(),
            str(message_file),
            "-f",
            "cine.md",
        ],
        check=True,
    )
    _utils.ntfy_notification()


if __name__ == "__main__":
    main()
