"""Repository layer for singleton platform settings."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSettings

DEFAULT_PLATFORM_SETTINGS_KEY = "default"


class PlatformSettingsRepository:
    """Data access methods for mutable platform settings."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> PlatformSettings | None:
        """Return the singleton settings row when present."""
        return self.session.scalar(
            select(PlatformSettings).where(
                PlatformSettings.singleton_key == DEFAULT_PLATFORM_SETTINGS_KEY
            )
        )

    def get_effective_allow_open_registration(self, *, default_value: bool) -> bool:
        """Resolve the stored registration policy or fall back to env defaults."""
        entity = self.get()
        if entity is None:
            return default_value
        return entity.allow_open_registration

    def set_allow_open_registration(self, *, value: bool, default_value: bool) -> PlatformSettings:
        """Persist the registration policy in the singleton settings row."""
        entity = self.get()
        if entity is None:
            entity = PlatformSettings(
                singleton_key=DEFAULT_PLATFORM_SETTINGS_KEY,
                allow_open_registration=default_value,
            )
            self.session.add(entity)

        entity.allow_open_registration = value
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
