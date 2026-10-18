import hashlib
import io
import json
from contextlib import contextmanager
from pathlib import Path
import shutil
import tarfile
import unittest
from unittest.mock import patch
import uuid

import download_models as models


def spec(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@contextmanager
def temporary_directory():
    # Use the workspace so tests also run in restricted Windows sandboxes.
    root = Path(__file__).resolve().parent
    directory = root / f".test-{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield str(directory)
    finally:
        if directory.resolve().parent != root:
            raise ValueError("Test cleanup escaped the test workspace")
        shutil.rmtree(directory)


class ModelDownloadTests(unittest.TestCase):
    def test_bad_download_preserves_existing_file(self):
        with temporary_directory() as temp:
            target = Path(temp) / "model.onnx"
            target.write_bytes(b"old model")
            with self.assertRaises(ValueError):
                models.install(io.BytesIO(b"corrupt"), target, spec(b"expected"))
            self.assertEqual(target.read_bytes(), b"old model")
            self.assertFalse(target.with_name("model.onnx.part").exists())

    def test_archive_installs_only_manifest_files(self):
        with temporary_directory() as temp:
            root = Path(temp)
            archive = root / "models.tar.bz2"
            with tarfile.open(archive, "w:bz2") as tar:
                for name, data in [("package/model.onnx", b"weight"),
                                   ("package/../../escape.txt", b"bad"),
                                   ("package/test_wavs/sample.wav", b"sample")]:
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    tar.addfile(member, io.BytesIO(data))
            group = {"directory": "package", "archive_root": "package",
                     "files": {"model.onnx": spec(b"weight")}}
            with archive.open("rb") as source:
                models.install_archive(source, root / "models", group, ["model.onnx"])
            self.assertEqual((root / "models/package/model.onnx").read_bytes(), b"weight")
            self.assertFalse((root / "escape.txt").exists())
            self.assertFalse((root / "models/package/test_wavs").exists())

    def test_check_missing_model_does_not_download(self):
        with temporary_directory() as temp, patch("download_models.download") as download:
            result = models.main(["--check", "--only", "vad", "--model-dir", temp])
            self.assertEqual(result, 1)
            download.assert_not_called()

    def test_verified_model_is_reused(self):
        with temporary_directory() as temp:
            root = Path(temp)
            (root / "model.onnx").write_bytes(b"weight")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"vad": {"directory": "", "files": {"model.onnx": spec(b"weight")}}}))
            with patch("download_models.MANIFEST", manifest), patch("download_models.download") as download:
                self.assertEqual(models.main(["--only", "vad", "--model-dir", temp]), 0)
                download.assert_not_called()

    def test_full_download_and_install_with_local_source(self):
        with temporary_directory() as temp:
            root = Path(temp)
            source = root / "source.onnx"
            source.write_bytes(b"downloaded weight")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"vad": {
                "directory": "", "urls": {"model.onnx": source.as_uri()},
                "files": {"model.onnx": spec(source.read_bytes())}}}))
            with patch("download_models.MANIFEST", manifest):
                self.assertEqual(models.main(["--only", "vad", "--model-dir", str(root / "models")]), 0)
                self.assertTrue(models.valid(root / "models/model.onnx", spec(source.read_bytes())))


if __name__ == "__main__":
    unittest.main()
