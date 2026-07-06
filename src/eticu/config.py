from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    intervals_api_key: str = ""
    intervals_athlete_id: str = ""

    @property
    def base_url(self) -> str:
        return f"https://intervals.icu/api/v1/athlete/{self.intervals_athlete_id}"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
