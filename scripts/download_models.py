"""Download official model files, verify SHA-256, and install atomically.

No third-party Python packages required. Existing valid weights are reused.
"""
import argparse
import hashlib
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).with_name("models.json")
CHUNK = 1024 * 1024


def valid(path, spec):
    if not path.is_file() or path.stat().st_size != spec["size"]:
        return False
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == spec["sha256"]


def install(source, target, spec):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with partial.open("wb") as dest:
            copied = 0
            report_at = 64 * CHUNK
            while chunk := source.read(CHUNK):
                dest.write(chunk)
                copied += len(chunk)
                if copied >= report_at:
                    print(f"  {target.name}: {copied / CHUNK:.0f} MiB", flush=True)
                    report_at = copied + 64 * CHUNK
        if not valid(partial, spec):
            raise ValueError(f"Checksum or size mismatch: {target.name}")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def download(url):
    print(f"Downloading {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "whisper-toolkit/1.0"})
    return urllib.request.urlopen(request, timeout=120)


def install_archive(archive, model_dir, group, needed):
    # Read only manifest-listed regular files; never extract archive paths or links.
    remaining = set(needed)
    prefix = group["archive_root"] + "/"
    with tarfile.open(fileobj=archive, mode="r|bz2") as tar:
        for member in tar:
            name = member.name.removeprefix("./")
            if not member.isfile() or not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if relative not in remaining:
                continue
            with tar.extractfile(member) as source:
                install(source, model_dir / group["directory"] / relative, group["files"][relative])
            remaining.remove(relative)
            if not remaining:
                break
    if remaining:
        raise ValueError(f"Archive missing files: {', '.join(sorted(remaining))}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=["sensevoice", "nano", "whisper", "vad"])
    parser.add_argument("--check", action="store_true", help="verify local files without downloading")
    parser.add_argument("--list", action="store_true", help="show model groups and download sources")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failed = False
    selected = list(dict.fromkeys(args.only or manifest))
    if "nano" in selected and "sensevoice" not in selected:
        selected.append("sensevoice")
    if any(name in selected for name in ("sensevoice", "nano")) and "vad" not in selected:
        selected.append("vad")
    for name in selected:
        group = manifest[name]
        if args.list:
            print(f"{name}: {sum(spec['size'] for spec in group['files'].values()) / 1024**3:.2f} GiB")
            for url in group.get("urls", {}).values() or [group["url"]]:
                print(f"  {url}")
            continue
        directory = args.model_dir / group["directory"]
        needed = [file for file, spec in group["files"].items() if not valid(directory / file, spec)]
        if not needed:
            print(f"{name}: all files verified; nothing to download.")
            continue
        if args.check:
            print(f"{name}: missing or invalid: {', '.join(needed)}", file=sys.stderr)
            failed = True
            continue
        if "archive_root" in group:
            with download(group["url"]) as source:
                install_archive(source, args.model_dir, group, needed)
        else:
            for file in needed:
                with download(group["urls"][file]) as source:
                    install(source, directory / file, group["files"][file])
        print(f"{name}: installed and verified.")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, tarfile.TarError) as error:
        sys.exit(f"Model download failed: {error}")
