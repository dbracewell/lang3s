import hashlib
import json
import os
import sys
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest_path = Path(os.environ.get("FILESTORE_MANIFEST", "/manifest.json"))
    artifacts_root = Path(os.environ.get("FILESTORE_ARTIFACTS", "/manifest_data"))
    with manifest_path.open() as file:
        manifest = json.load(file)
    for artifact in manifest["artifacts"]:
        path = artifacts_root / artifact["path"]
        if not path.is_file() or path.stat().st_size != artifact["size"]:
            print(f"Invalid artifact: {artifact['path']}")
            return 1
        if checksum(path) != artifact["sha256"]:
            print(f"Checksum mismatch: {artifact['path']}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
