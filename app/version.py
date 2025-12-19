"""Version retrieval for Forgetful."""

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Get version from installed package or fallback to _version.py."""
    try:
        return version("forgetful-ai")
    except PackageNotFoundError:
        try:
            from app._version import __version__

            return __version__
        except ImportError:
            return "0.0.0-dev"
