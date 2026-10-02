import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from orthodb_cli.cache import ManifestEntry, download_entry, find_cached_file, md5sum, parse_manifest, resolve_dataset, save_manifest
from orthodb_cli.cli import is_large, main
from orthodb_cli.errors import OrthoDBError


HTML = """
<table>
<tr><th>File</th><th>Size</th><th>Description</th><th>MD5sum</th></tr>
<tr>
  <td><a href=https://data.orthodb.org/current/download/odb_data_dump/odb12v2_species.tab.gz>odb12v2_species.tab.gz</a></td>
  <td>0.6 MB</td>
  <td>Ortho DB organism ids</td>
  <td>05f75664f4e1ed9af3ac7aa19ca68d8f</td>
</tr>
<tr>
  <td><a href=https://data.orthodb.org/current/download/odb_data_dump/odb12v2_level2species.tab.gz>odb12v2_level2species.tab.gz</a></td>
  <td>240.8 kB</td>
  <td>correspondence between level ids and organism ids</td>
  <td>c6b7f73ac554d1cae3df2d2a6eb9fdce</td>
</tr>
</table>
"""


class CacheTests(unittest.TestCase):
    def test_parse_manifest(self):
        entries = parse_manifest(HTML)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].name, "odb12v2_species.tab.gz")
        self.assertEqual(entries[0].size, "0.6 MB")
        self.assertEqual(entries[0].md5, "05f75664f4e1ed9af3ac7aa19ca68d8f")

    def test_resolve_dataset_alias(self):
        entry = resolve_dataset(parse_manifest(HTML), "species")

        self.assertEqual(entry.name, "odb12v2_species.tab.gz")

    def test_large_size_detection(self):
        self.assertTrue(is_large("4.5 GB"))
        self.assertFalse(is_large("128.2 MB"))

    def test_cached_file_matches_the_manifest_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            for name, alias in (("odb12v2_level2species.tab.gz", "species"), ("odb12v2_og_aa_fasta.gz", "aa_fasta")):
                with self.subTest(alias=alias):
                    (cache_dir / name).touch()
                    self.assertIsNone(find_cached_file(cache_dir, alias))
                    suffix = "species.tab.gz" if alias == "species" else "aa_fasta.gz"
                    path = cache_dir / f"odb12v2_{suffix}"
                    path.touch()
                    self.assertEqual(find_cached_file(cache_dir, alias), path)
                    entries = [ManifestEntry(item.name, "", "", "", "") for item in cache_dir.iterdir()]
                    self.assertEqual(resolve_dataset(entries, alias).name, path.name)
                    self.assertEqual(find_cached_file(cache_dir, path.name), path)
                    self.assertIsNone(find_cached_file(cache_dir, suffix))

    def test_ambiguous_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            entries = []
            for name in ("odb12v1_species.tab.gz", "odb12v2_species.tab.gz"):
                (cache_dir / name).touch()
                entries.append(ManifestEntry(name, "", "", "", ""))
            with self.assertRaisesRegex(OrthoDBError, "multiple"):
                find_cached_file(cache_dir, "species")
            with self.assertRaisesRegex(OrthoDBError, "multiple"):
                resolve_dataset(entries, "species")


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache_dir = self.root / "cache"
        self.payload = b"download fixture\n" * 70000
        self.source = self.root / "source"
        self.source.write_bytes(self.payload)
        self.entry = ManifestEntry(
            "odb12v2_species.tab.gz", self.source.as_uri(), "1.1 MB", "fixture", md5sum(self.source)
        )
        self.destination = self.cache_dir / self.entry.name

    def test_downloads_fresh_files_and_replaces_corrupt_files(self):
        for existing, verify in ((None, True), (None, False), (b"corrupt", True)):
            with self.subTest(existing=existing, verify=verify):
                self.cache_dir.mkdir(exist_ok=True)
                self.destination.unlink(missing_ok=True)
                if existing is not None:
                    self.destination.write_bytes(existing)

                entry = self.entry if verify else replace(self.entry, md5="0" * 32)
                result = download_entry(entry, self.cache_dir, verify=verify)

                self.assertEqual(result, self.destination)
                self.assertEqual(result.read_bytes(), self.payload)
                self.assertEqual(md5sum(result), self.entry.md5)
                self.assertEqual(list(self.cache_dir.iterdir()), [self.destination])

    def test_reuses_valid_cache_or_skips_verification_when_requested(self):
        self.cache_dir.mkdir()
        for content, verify in ((self.payload, True), (b"unverified", False)):
            with self.subTest(verify=verify):
                self.destination.write_bytes(content)
                with patch("orthodb_cli.cache.urlopen") as request:
                    self.assertEqual(download_entry(self.entry, self.cache_dir, verify=verify), self.destination)
                request.assert_not_called()
                self.assertEqual(self.destination.read_bytes(), content)
                self.assertEqual(list(self.cache_dir.iterdir()), [self.destination])

    def test_invalid_url_does_not_create_a_partial_file(self):
        with self.assertRaises(ValueError):
            download_entry(replace(self.entry, url="invalid URL"), self.cache_dir)
        self.assertEqual(list(self.cache_dir.iterdir()), [])

    def test_failures_preserve_existing_file_and_release_resources(self):
        self.cache_dir.mkdir()
        create_temporary = tempfile.NamedTemporaryFile
        for stage in ("request", "read", "write", "checksum", "hash", "replace", "interrupt"):
            with self.subTest(stage=stage), ExitStack() as stack:
                self.destination.write_bytes(b"existing data")
                response = io.BytesIO(self.payload)
                stack.callback(response.close)
                created = []
                failure = KeyboardInterrupt() if stage == "interrupt" else OSError(f"{stage} failed")

                def capture_temporary(*args, **kwargs):
                    out = create_temporary(*args, **kwargs)
                    created.append(out)
                    if stage == "write":
                        stack.enter_context(patch.object(out, "write", side_effect=failure))
                    return out

                stack.enter_context(patch("orthodb_cli.cache.tempfile.NamedTemporaryFile", side_effect=capture_temporary))
                request = stack.enter_context(patch("orthodb_cli.cache.urlopen", return_value=response))
                entry = self.entry
                if stage == "request":
                    request.side_effect = failure
                elif stage in {"read", "interrupt"}:
                    stack.enter_context(patch.object(response, "read", side_effect=[b"partial", failure]))
                elif stage == "checksum":
                    entry = replace(self.entry, md5="0" * 32)
                elif stage == "hash":
                    stack.enter_context(patch("orthodb_cli.cache.md5sum", side_effect=["old checksum", failure]))
                elif stage == "replace":
                    stack.enter_context(patch.object(Path, "replace", side_effect=failure))

                expected = OrthoDBError if stage == "checksum" else type(failure)
                with self.assertRaises(expected) as caught:
                    download_entry(entry, self.cache_dir)

                if stage == "checksum":
                    self.assertIn("MD5 mismatch", str(caught.exception))
                else:
                    self.assertIs(caught.exception, failure)
                self.assertEqual(self.destination.read_bytes(), b"existing data")
                self.assertEqual(list(self.cache_dir.iterdir()), [self.destination])
                self.assertEqual(len(created), 1)
                self.assertTrue(created[0].closed)
                if stage != "request":
                    self.assertTrue(response.closed)

    def test_cli_download_and_sync(self):
        entries = [
            replace(self.entry, name=f"odb12v2_{alias}.tab.gz")
            for alias in ("species", "levels", "level2species")
        ]
        commands = (("download", "species"), ("download", "species", "--no-verify"), ("sync", "minimal"))
        for index, command in enumerate(commands):
            with self.subTest(command=command):
                cache_dir = self.root / f"cli-{index}"
                save_manifest(entries, cache_dir)
                result = subprocess.run(
                    [sys.executable, "-m", "orthodb_cli.cli", "--cache-dir", str(cache_dir), "cache", *command],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                output = json.loads(result.stdout)
                expected = entries if command[0] == "sync" else entries[:1]
                if command[0] == "sync":
                    self.assertEqual([item["name"] for item in output["downloaded"]], [item.name for item in expected])
                else:
                    self.assertEqual(output["name"], self.entry.name)
                for entry in expected:
                    self.assertEqual((cache_dir / entry.name).read_bytes(), self.payload)
                self.assertEqual({path.name for path in cache_dir.iterdir()}, {"manifest.json", *(item.name for item in expected)})

    def test_cli_routes_timeout_to_all_cache_requests(self):
        entries = [replace(self.entry, name=f"odb12v2_{alias}.tab.gz") for alias in ("species", "levels", "level2species")]
        commands = (
            ("manifest",), ("manifest", "--refresh"), ("status",), ("status", "--refresh"),
            ("plan", "minimal"), ("download", "species"), ("sync", "minimal"),
        )
        for index, command in enumerate(commands):
            with self.subTest(command=command):
                cache_dir = self.root / f"timeout-{index}"
                with patch("orthodb_cli.cli.fetch_manifest", return_value=entries) as refreshed, patch(
                    "orthodb_cli.cache.fetch_manifest", return_value=entries
                ) as loaded, patch("orthodb_cli.cache.urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(self.payload)) as request, redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--cache-dir", str(cache_dir), "--timeout", "2.5", "cache", *command]), 0)
                manifest = refreshed if "--refresh" in command else loaded
                manifest.assert_called_once_with(timeout=2.5)
                for call in request.call_args_list:
                    self.assertEqual(call.kwargs["timeout"], 2.5)
                expected_requests = 3 if command[0] == "sync" else int(command[0] == "download")
                self.assertEqual(request.call_count, expected_requests)

    def test_cli_rejects_invalid_timeouts(self):
        for timeout in ("0", "-1", "nan", "inf"):
            with self.subTest(timeout=timeout), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(["--timeout", timeout, "cache", "dir"])
            self.assertEqual(caught.exception.code, 2)

    def test_sync_large_file_gate_and_presence_plan(self):
        entries = [replace(self.entry, name=f"odb12v2_{alias}.tab.gz") for alias in ("species", "levels", "level2species")]
        entries[0] = replace(entries[0], size="2 GB")
        save_manifest(entries, self.cache_dir)
        output = io.StringIO()
        with patch("orthodb_cli.cache.urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(self.payload)) as request, redirect_stdout(output):
            self.assertEqual(main(["--cache-dir", str(self.cache_dir), "cache", "sync", "minimal"]), 0)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(json.loads(output.getvalue())["skipped"][0]["dataset"], "species")
        self.assertFalse(self.destination.exists())

        output = io.StringIO()
        with patch("orthodb_cli.cache.md5sum", side_effect=AssertionError("plan must not hash files")), redirect_stdout(output):
            self.assertEqual(main(["--cache-dir", str(self.cache_dir), "cache", "plan", "minimal", "--include-large"]), 0)
        plan = json.loads(output.getvalue())["datasets"]
        self.assertTrue(plan[0]["will_download"])
        self.assertFalse(plan[1]["will_download"])
        self.assertTrue(plan[1]["downloaded"])

        output = io.StringIO()
        with patch("orthodb_cli.cache.urlopen", return_value=io.BytesIO(self.payload)) as request, redirect_stdout(output):
            self.assertEqual(main(["--cache-dir", str(self.cache_dir), "cache", "sync", "minimal", "--include-large"]), 0)
        request.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())["skipped"], [])
        self.assertEqual(self.destination.read_bytes(), self.payload)

    def test_cleanup_failure_preserves_the_original_error(self):
        for failure in (KeyboardInterrupt(), OSError("request failed"), OrthoDBError("download failed")):
            with self.subTest(failure=type(failure).__name__), patch(
                "orthodb_cli.cache.urlopen", side_effect=failure
            ), patch.object(Path, "unlink", side_effect=PermissionError("cleanup denied")):
                with self.assertRaises(type(failure)) as caught:
                    download_entry(self.entry, self.cache_dir)
                self.assertIs(caught.exception, failure)
                self.assertIn("cleanup denied", failure.__notes__[0])
                self.assertIn(".part", failure.__notes__[0])

    def test_successful_replacement_needs_no_cleanup(self):
        with patch.object(Path, "unlink", side_effect=PermissionError("cleanup denied")) as cleanup:
            result = download_entry(self.entry, self.cache_dir)
        cleanup.assert_not_called()
        self.assertEqual(result.read_bytes(), self.payload)

    def test_cli_reports_cleanup_failure_without_losing_interruption(self):
        save_manifest([self.entry], self.cache_dir)
        for failure, status, message in (
            (KeyboardInterrupt(), 130, "orthodb: interrupted"),
            (OrthoDBError("download failed"), 1, "orthodb: error: download failed"),
            (OSError("request failed"), 1, "orthodb: error: request failed"),
        ):
            with self.subTest(failure=type(failure).__name__):
                stderr = io.StringIO()
                with patch("orthodb_cli.cache.urlopen", side_effect=failure), patch.object(
                    Path, "unlink", side_effect=PermissionError("cleanup denied")
                ), redirect_stderr(stderr):
                    self.assertEqual(main(["--cache-dir", str(self.cache_dir), "cache", "download", "species"]), status)
                self.assertIn(message, stderr.getvalue())
                self.assertIn("cleanup denied", stderr.getvalue())
                self.assertIn(".part", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
