from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

UploadFile = Callable[[Path, str, str], bool]


class DownloadBlobLike(Protocol):
    @property
    def name(self) -> str: ...

    def download_to_filename(self, filename: str) -> None: ...


class DownloadStorageClientLike(Protocol):
    def list_blobs(
        self, bucket_name: str, *, prefix: str
    ) -> Iterable[DownloadBlobLike]: ...


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


def _download_atomically(blob: DownloadBlobLike, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}-",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        blob.download_to_filename(str(temporary_path))
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def sync_latest_listed_issues_artifact(
    bucket_name: str,
    output_root: Path,
    *,
    storage_client: DownloadStorageClientLike | None = None,
) -> bool:
    """Restore the latest completed JPX artifact to an ephemeral work directory."""
    client = storage_client or cast(DownloadStorageClientLike, storage.Client())
    prefix = "jpx/listed_issues/"
    pattern = re.compile(
        r"^jpx/listed_issues/snapshot_date=\d{4}-\d{2}-\d{2}/"
        r"ingested_at=[^/]+/manifest\.json$"
    )
    blobs = {
        blob.name: blob
        for blob in client.list_blobs(bucket_name, prefix=prefix)
        if blob.name.endswith(("/manifest.json", "/data.parquet"))
    }
    manifests = sorted(name for name in blobs if pattern.fullmatch(name))
    if not manifests:
        return False

    manifest_object = manifests[-1]
    parquet_object = manifest_object.removesuffix("manifest.json") + "data.parquet"
    if parquet_object not in blobs:
        raise FileNotFoundError(
            f"JPX manifestに対応するGCS Parquetがありません: {parquet_object}"
        )

    manifest_path = output_root / manifest_object
    parquet_path = output_root / parquet_object
    if not manifest_path.is_file():
        _download_atomically(blobs[manifest_object], manifest_path)
    if not parquet_path.is_file():
        _download_atomically(blobs[parquet_object], parquet_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != _sha256(parquet_path):
        raise ValueError(
            f"GCSから復元したJPX ParquetのSHA-256が一致しません: {parquet_path}"
        )
    return True
