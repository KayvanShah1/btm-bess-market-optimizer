import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_root(
    markers: tuple[str, ...] = ("data", ".git", ".env"),
) -> Path:
    """
    Search upwards from the current file's directory to find the project root.

    This avoids fragile Path.parents[n] assumptions when files are moved, and
    keeps deployed app installs from resolving data paths inside site-packages.
    """
    env_root = os.getenv("BESS_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    seen: set[Path] = set()
    starts = (Path.cwd().resolve(), Path(__file__).resolve().parent)

    for start in starts:
        for parent in [start] + list(start.parents):
            if parent in seen:
                continue
            seen.add(parent)
            if any((parent / marker).exists() for marker in markers):
                return parent

    return Path.cwd().resolve()


PROJECT_ROOT = find_project_root()


class BaseProjectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_dump(self, **kwargs):
        """Custom dump to make absolute paths relative for clean logging."""
        dump = super().model_dump(**kwargs)
        project_root = getattr(self, "project_root", PROJECT_ROOT)
        for key, value in dump.items():
            if isinstance(value, Path) and value.is_absolute():
                try:
                    dump[key] = str(value.relative_to(project_root))
                except ValueError:
                    dump[key] = str(value)
        return dump


class Settings(BaseProjectSettings):
    """
    Application settings.

    This class is a singleton and should be imported directly from this module.
    """

    project_root: Path = PROJECT_ROOT
    data_dir: Path = project_root / "data"
    raw_data_dir: Path = data_dir / "raw"
    processed_data_dir: Path = data_dir / "processed"
    final_data_dir: Path = data_dir / "final"
    output_dir: Path = data_dir / "output"

    def model_post_init(self, __context):
        """Ensure directories exist on startup."""
        for directory in [
            self.data_dir,
            self.raw_data_dir,
            self.processed_data_dir,
            self.final_data_dir,
            self.output_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Instantiate the singleton
settings = Settings()

if __name__ == "__main__":
    from rich.pretty import pprint

    pprint(settings.model_dump())
