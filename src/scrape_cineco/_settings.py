from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    local_tmp_dir: Path = "data/_tmp_"
    aws_profile: str = "personal"
    # secrets
    # TODO should I have a bucket for all the scrape data? This would allow better
    #      permissions (just write to the bucket)
    bucket: SecretStr

    model_config = SettingsConfigDict(
        env_file=(".env",), extra="ignore", hide_input_in_errors=True
    )

    def model_post_init(self, __context: Any) -> None:
        self.local_tmp_dir.mkdir(exist_ok=True, parents=True)


settings = Settings()
