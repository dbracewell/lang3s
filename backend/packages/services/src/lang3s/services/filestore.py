"""Verify and sync local LLM artifacts from the checked-in manifest."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from lang3s.core import config
from lang3s.llm import LOCAL_MODELS

EMBEDDING_ARTIFACTS = {
    "models/embedding/config.json",
    "models/embedding/model.safetensors",
    "models/embedding/nli_compressed.pt",
    "models/embedding/search_compressed.pt",
    "models/embedding/search_layers.pt",
    "models/embedding/special_tokens_map.json",
    "models/embedding/tokenizer.json",
    "models/embedding/tokenizer_config.json",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> list[dict[str, object]]:
    with path.open() as file:
        manifest = json.load(file)
    if manifest.get("version") != 1 or not isinstance(manifest.get("artifacts"), list):
        raise ValueError(f"Invalid artifact manifest: {path}")
    return manifest["artifacts"]


def registry_paths() -> set[str]:
    paths = set(EMBEDDING_ARTIFACTS)
    for model in LOCAL_MODELS.values():
        paths.add(f"models/locallm/{model.filename}")
        paths.update(
            f"models/locallm/adapters/{adapter.filename}"
            for adapter in model.adapters
        )
    return paths


def verify(manifest_path: Path, filestore_root: Path) -> bool:
    artifacts = load_manifest(manifest_path)
    manifest_paths = {str(item["path"]) for item in artifacts}
    if manifest_paths != registry_paths():
        raise ValueError("Manifest artifacts do not match the local-model registry")

    valid = True
    for item in artifacts:
        relative_path = Path(str(item["path"]))
        target = filestore_root / relative_path
        expected_size = int(item["size"])
        expected_hash = str(item["sha256"])
        if not target.is_file():
            print(f"FAIL missing {relative_path}")
            valid = False
            continue
        if target.stat().st_size != expected_size:
            print(f"FAIL size mismatch {relative_path}")
            valid = False
            continue
        if sha256(target) != expected_hash:
            print(f"FAIL checksum mismatch {relative_path}")
            valid = False
            continue
        print(f"OK   {relative_path}")
    return valid


def sync(manifest_path: Path, filestore_root: Path, source: str) -> bool:
    artifacts = load_manifest(manifest_path)
    source_url = urlparse(source)
    for item in artifacts:
        relative_path = Path(str(item["path"]))
        target = filestore_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            if source_url.scheme in {"http", "https"}:
                artifact_url = f"{source.rstrip('/')}/{relative_path.as_posix()}"
                with urlopen(artifact_url) as response:
                    shutil.copyfileobj(response, temporary)
            else:
                with (Path(source) / relative_path).open("rb") as input_file:
                    shutil.copyfileobj(input_file, temporary)
        expected_hash = str(item["sha256"])
        valid_size = temporary_path.stat().st_size == int(item["size"])
        valid_hash = sha256(temporary_path) == expected_hash
        if not valid_size or not valid_hash:
            temporary_path.unlink(missing_ok=True)
            raise ValueError(
                f"Downloaded artifact failed verification: {relative_path}"
            )
        temporary_path.replace(target)
        print(f"SYNC {relative_path}")
    return verify(manifest_path, filestore_root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify or sync Lang3s local LLM artifacts"
    )
    parser.add_argument("command", choices=("verify", "sync"))
    parser.add_argument("--source", help="Local directory or HTTPS base URL for sync")
    parser.add_argument("--filestore", type=Path, default=config.FILESTORE_ROOT)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repo_root() / "artifacts" / "filestore-manifest.json",
    )
    args = parser.parse_args()
    if args.command == "sync" and not args.source:
        parser.error("sync requires --source")
    try:
        success = (
            sync(args.manifest, args.filestore, args.source)
            if args.command == "sync"
            else verify(args.manifest, args.filestore)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 1
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
