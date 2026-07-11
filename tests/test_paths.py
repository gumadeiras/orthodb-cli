from pathlib import Path
import unittest

from orthodb_cli.cache import default_cache_dir
from orthodb_cli.cli import build_parser
from orthodb_cli.paths import default_data_dir


class PathTests(unittest.TestCase):
    def test_default_data_dir_uses_os_location(self) -> None:
        home = Path("/Users/gustavo")
        self.assertEqual(
            default_data_dir(environ={}, platform="darwin", home=home),
            home / "Library" / "Application Support" / "orthodb",
        )
        self.assertEqual(
            default_data_dir(
                environ={"XDG_DATA_HOME": "/var/data"},
                platform="linux",
                home=Path("/home/gustavo"),
            ),
            Path("/var/data/orthodb"),
        )
        self.assertEqual(
            default_data_dir(
                environ={"LOCALAPPDATA": r"C:\Users\gustavo\AppData\Local"},
                platform="win32",
                home=Path(r"C:\Users\gustavo"),
            ),
            Path(r"C:\Users\gustavo\AppData\Local") / "orthodb",
        )

    def test_relative_xdg_data_home_is_ignored(self) -> None:
        home = Path("/home/gustavo")
        self.assertEqual(
            default_data_dir(
                environ={"XDG_DATA_HOME": "relative"},
                platform="linux",
                home=home,
            ),
            home / ".local" / "share" / "orthodb",
        )

    def test_cli_default_routes_to_persistent_data(self) -> None:
        args = build_parser().parse_args(["cache", "dir"])
        self.assertTrue(default_cache_dir().is_absolute())
        self.assertEqual(Path(args.cache_dir), default_cache_dir())


if __name__ == "__main__":
    unittest.main()
