from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

UploadFile = Callable[[Path, str, str], bool]


@dataclass(frozen=True)
class RawArtifact:
    parquet_path: Path
    manifest_path: Path
    parquet_object: str
    manifest_object: str


@dataclass(frozen=True)
class GcsPublishResult:
    uploaded_count: int
    skipped_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_artifacts(source_dir: Path) -> list[RawArtifact]:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"rawデータdirectoryが見つかりません: {source_dir}")

    parquet_paths = sorted(source_dir.rglob("data.parquet"))
    if not parquet_paths:
        raise FileNotFoundError(f"data.parquetが見つかりません: {source_dir}")

    artifacts: list[RawArtifact] = []
    for parquet_path in parquet_paths:
        manifest_path = parquet_path.with_name("manifest.json")
        if not manifest_path.is_file():
            raise FileNotFoundError(f"manifest.jsonが見つかりません: {parquet_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_hash = manifest.get("sha256")
        if not isinstance(expected_hash, str) or _sha256(parquet_path) != expected_hash:
            raise ValueError(
                f"ParquetのSHA-256がmanifestと一致しません: {parquet_path}"
            )

        artifacts.append(
            RawArtifact(
                parquet_path=parquet_path,
                manifest_path=manifest_path,
                parquet_object=parquet_path.relative_to(source_dir).as_posix(),
                manifest_object=manifest_path.relative_to(source_dir).as_posix(),
            )
        )
    return artifacts


def _gcs_uploader(bucket_name: str) -> UploadFile:
    bucket = storage.Client().bucket(bucket_name)

    def upload_file(source_path: Path, object_name: str, content_type: str) -> bool:
        blob = bucket.blob(object_name)
        try:
            blob.upload_from_filename(
                source_path,
                content_type=content_type,
                if_generation_match=0,
            )
        except PreconditionFailed:
            return False
        return True

    return upload_file


def publish_raw_artifacts(
    source_dir: Path,
    bucket_name: str,
    *,
    upload_file: UploadFile | None = None,
) -> GcsPublishResult:
    artifacts = _validated_artifacts(source_dir)
    uploader = upload_file or _gcs_uploader(bucket_name)

    uploaded_count = 0
    skipped_count = 0
    for artifact in artifacts:
        files = (
            (
                artifact.parquet_path,
                artifact.parquet_object,
                "application/vnd.apache.parquet",
            ),
            (artifact.manifest_path, artifact.manifest_object, "application/json"),
        )
        for source_path, object_name, content_type in files:
            if uploader(source_path, object_name, content_type):
                uploaded_count += 1
            else:
                skipped_count += 1

    return GcsPublishResult(
        uploaded_count=uploaded_count,
        skipped_count=skipped_count,
    )
