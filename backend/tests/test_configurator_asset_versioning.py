from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from configurator_asset_versioning import (
    _require_admin,
    create_publication_revision,
    make_asset_version_router,
    snapshot_asset,
    snapshot_before_upload,
)


class FakeCursor:
    def __init__(self, documents):
        self.documents = [doc.copy() for doc in documents]

    def sort(self, *_args, **_kwargs):
        self.documents.sort(key=lambda item: item.get("revision_created_at", ""), reverse=True)
        return self

    async def to_list(self, _limit):
        return [doc.copy() for doc in self.documents]


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = documents or []

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document.copy()
        return None

    def find(self, query, *_args, **_kwargs):
        return FakeCursor(
            [document for document in self.documents if all(document.get(key) == value for key, value in query.items())]
        )

    async def insert_one(self, document):
        self.documents.append(document.copy())
        return SimpleNamespace(inserted_id=document.get("revision_id"))


class FakeAssetCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, query, *_args, **_kwargs):
        if query.get("asset_id") == self.document.get("asset_id"):
            return self.document.copy()
        return None

    async def replace_one(self, _query, document, upsert=False):
        self.document = document.copy()
        return SimpleNamespace(matched_count=1, upserted_id=None)


class FakeDB:
    def __init__(self, asset, revisions):
        self.configurator_assets = FakeAssetCollection(asset)
        self.configurator_asset_versions = FakeCollection(revisions)


@pytest.fixture
def client():
    now = datetime.now(timezone.utc).isoformat()
    current = {
        "asset_id": "asset-1",
        "variant_id": "variant-1",
        "version": "2.0.0",
        "storage_key": "configurator/asset-1/v2.0.0/current.glb",
        "checksum_sha256": "b" * 64,
        "file_size_bytes": 200,
        "validation_passed": True,
        "admin_reviewed": True,
        "published": True,
        "storage_status": "PUBLISHED",
        "created_at": now,
        "updated_at": now,
    }
    revision = {
        "asset_id": "asset-1",
        "revision_id": "rev-12345678",
        "variant_id": "variant-1",
        "version": "1.0.0",
        "storage_key": "configurator/asset-1/v1.0.0/legacy.glb",
        "checksum_sha256": "a" * 64,
        "file_size_bytes": 100,
        "validation_passed": True,
        "admin_reviewed": True,
        "published": True,
        "storage_status": "PUBLISHED",
        "review_notes": "approved",
        "revision_created_at": now,
    }
    db = FakeDB(current, [revision])
    app = FastAPI()
    app.include_router(make_asset_version_router(db))

    async def fake_admin():
        return "admin"

    app.dependency_overrides[_require_admin] = fake_admin
    return TestClient(app), db


def test_snapshot_is_immutable_copy():
    asset = {"asset_id": "asset-1", "nested": {"value": 1}}
    revision = snapshot_asset(
        asset,
        revision_id="rev-12345678",
        snapshot_type="UPLOAD_SOURCE",
        created_at="2026-09-12T00:00:00+00:00",
    )
    asset["nested"]["value"] = 99
    assert revision["asset_id"] == "asset-1"
    assert revision["nested"]["value"] == 1
    assert revision["revision_id"] == "rev-12345678"
    assert revision["snapshot_type"] == "UPLOAD_SOURCE"
    assert "_id" not in revision


@pytest.mark.asyncio
async def test_snapshot_before_upload_captures_only_verified_assets():
    now = datetime.now(timezone.utc).isoformat()
    verified = {
        "asset_id": "asset-1",
        "storage_key": "configurator/asset-1/v1.0.0/current.glb",
        "checksum_sha256": "a" * 64,
        "validation_passed": True,
        "nested": {"material": "MAT_PAINT"},
    }
    db = SimpleNamespace(configurator_asset_versions=FakeCollection())

    revision_id = await snapshot_before_upload(db, verified)

    assert revision_id
    assert len(db.configurator_asset_versions.documents) == 1
    verified["nested"]["material"] = "MUTATED"
    assert db.configurator_asset_versions.documents[0]["nested"]["material"] == "MAT_PAINT"

    unverified = {**verified, "validation_passed": False}
    assert await snapshot_before_upload(db, unverified) is None
    assert len(db.configurator_asset_versions.documents) == 1


@pytest.mark.asyncio
async def test_create_publication_revision_marks_runtime_authority():
    now = datetime.now(timezone.utc).isoformat()
    asset = {
        "asset_id": "asset-1",
        "variant_id": "variant-1",
        "version": "2.0.0",
        "storage_key": "configurator/asset-1/v2.0.0/current.glb",
        "checksum_sha256": "b" * 64,
        "file_size_bytes": 200,
        "validation_passed": True,
        "admin_reviewed": True,
        "published": False,
        "storage_status": "VALIDATED",
        "created_at": now,
        "updated_at": now,
    }
    db = SimpleNamespace(configurator_asset_versions=FakeCollection())

    revision_id = await create_publication_revision(db, asset)

    assert revision_id.startswith("rev-")
    revision = db.configurator_asset_versions.documents[0]
    assert revision["revision_id"] == revision_id
    assert revision["snapshot_type"] == "PUBLICATION"
    assert revision["active_revision_id"] == revision_id
    assert revision["published"] is True
    assert revision["storage_status"] == "PUBLISHED"
    assert revision["checksum_sha256"] == asset["checksum_sha256"]


def test_rollback_restores_reviewed_revision_and_preserves_current(client):
    test_client, db = client
    response = test_client.post(
        "/api/v1/admin/configurator/assets/asset-1/rollback",
        json={"revision_id": "rev-12345678"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["active_revision_id"] == "rev-12345678"
    assert payload["version"] == "1.0.0"
    assert db.configurator_assets.document["storage_key"].endswith("legacy.glb")
    assert len(db.configurator_asset_versions.documents) == 2
    assert db.configurator_asset_versions.documents[-1]["snapshot_type"] == "ROLLBACK_SOURCE"


def test_rollback_rejects_unreviewed_revision(client):
    test_client, db = client
    db.configurator_asset_versions.documents[0]["admin_reviewed"] = False
    response = test_client.post(
        "/api/v1/admin/configurator/assets/asset-1/rollback",
        json={"revision_id": "rev-12345678"},
    )
    assert response.status_code == 422
    assert db.configurator_assets.document["version"] == "2.0.0"
