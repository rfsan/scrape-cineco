from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    local_tmp_dir: Path = "data/_tmp_"
    # secrets
    bucket: SecretStr
    telegram_token: SecretStr

    model_config = SettingsConfigDict(
        env_file=(".env",), extra="ignore", hide_input_in_errors=True
    )

    def model_post_init(self, __context: Any) -> None:
        self.local_tmp_dir.mkdir(exist_ok=True, parents=True)


settings = Settings()
