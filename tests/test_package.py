import forge_os


def test_package_exposes_version() -> None:
    assert forge_os.__version__ == "0.1.0"
