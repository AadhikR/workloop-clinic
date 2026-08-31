from importlib.metadata import version

from app import __version__


def test_package_version() -> None:
    assert __version__ == version("workloop-api")
