import hashlib
import json
from pathlib import Path

import pytest
from google.api_core.exceptions import PreconditionFailed

from stock_analytics.publishing.gcs import _gcs_uploader, publish_raw_artifacts


def write_artifact(root: Path, content: bytes = b"parquet") -> tuple[Path, Path]:
    output_dir = root / "jquants" / "equity_daily_bars" / "trade_date=2026-08-14"
    output_dir.mkdir(parents=True)
    parquet_path = output_dir / "data.parquet"
    manifest_path = output_dir / "manifest.json"
    parquet_path.write_bytes(content)
    manifest_path.write_text(
        json.dumps({"sha256": hashlib.sha256(content).hexdigest()}),
        encoding="utf-8",
    )
    return parquet_path, manifest_path


def test_publish_raw_artifacts_uploads_only_validated_pair(tmp_path) -> None:
    source_dir = tmp_path / "raw"
    parquet_path, manifest_path = write_artifact(source_dir)
    (parquet_path.parent / "source.xls").write_bytes(b"source")
    uploads: list[tuple[Path, str, str]] = []

    def upload_file(path: Path, object_name: str, content_type: str) -> bool:
        uploads.append((path, object_name, content_type))
        return True

    result = publish_raw_artifacts(
        source_dir,
        "raw-bucket",
        upload_file=upload_file,
    )

    assert result.uploaded_count == 2
    assert result.skipped_count == 0
    assert uploads == [
        (
            parquet_path,
            "jquants/equity_daily_bars/trade_date=2026-08-14/data.parquet",
            "application/vnd.apache.parquet",
        ),
        (
            manifest_path,
            "jquants/equity_daily_bars/trade_date=2026-08-14/manifest.json",
            "application/json",
        ),
    ]


def test_publish_raw_artifacts_rejects_hash_mismatch_before_upload(tmp_path) -> None:
    source_dir = tmp_path / "raw"
    _, manifest_path = write_artifact(source_dir)
    manifest_path.write_text(json.dumps({"sha256": "invalid"}), encoding="utf-8")
    uploads: list[str] = []

    def upload_file(_path: Path, object_name: str, _content_type: str) -> bool:
        uploads.append(object_name)
        return True

    with pytest.raises(ValueError, match="SHA-256"):
        publish_raw_artifacts(
            source_dir,
            "raw-bucket",
            upload_file=upload_file,
        )

    assert uploads == []


def test_gcs_uploader_skips_existing_object(monkeypatch, tmp_path) -> None:
    class FakeBlob:
        def upload_from_filename(self, *_args, **_kwargs) -> None:
            raise PreconditionFailed("already exists")

    class FakeBucket:
        def blob(self, _object_name: str) -> FakeBlob:
            return FakeBlob()

    class FakeClient:
        def bucket(self, _bucket_name: str) -> FakeBucket:
            return FakeBucket()

    monkeypatch.setattr(
        "stock_analytics.publishing.gcs.storage.Client",
        FakeClient,
    )

    uploader = _gcs_uploader("raw-bucket")

    assert uploader(tmp_path / "data.parquet", "data.parquet", "test/type") is False
