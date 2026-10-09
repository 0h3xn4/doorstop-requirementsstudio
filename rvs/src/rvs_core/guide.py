"""Location of the bundled offline user guide."""

from importlib import resources
from pathlib import Path


def guide_path() -> Path | None:
    try:
        path = resources.files("rvs_core").joinpath("guide/guide.html")
        return Path(str(path)) if path.is_file() else None
    except (ModuleNotFoundError, FileNotFoundError):
        return None
