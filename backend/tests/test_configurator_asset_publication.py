from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from configurator_asset_admin_routes import _require_admin, make_asset_admin_router
from configurator_schemas import AssetEvidenceStatus, AssetEvidenceType


class Collection:
    def __init__(self, documents=None):
        self.documents = [document.copy() for document in (documents or [])]

    async def find_one(self, query, *_args, **_kwargs):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document.copy()
        return None

    async def update_one(self, query, update, *_args, **_kwargs):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                document.update(update.get("$set", {}))
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def replace_one(self, query, document, upsert=False):
        for index, current in enumerate(self.documents):
            if all(current.get(key) == value for key, value in query.items()):
                self.documents[index] = document.copy()
                return SimpleNamespace(matched_count=1, upserted_id=None)
        if upsert:
            self.documents.append(document.copy())
            return SimpleNamespace(matched_count=0, upserted_id=document.get("asset_id"))
        return SimpleNamespace(matched_count=0, upserted_id=None)

    async def insert_one(self, document):
        self.documents.append(document.copy())
        return SimpleNamespace(inserted_id=document.get("revision_id"))


class DB:
    def __init__(self):
        self.configurator_assets = Collection([{
            "asset_id": "asset-1",
            "variant_id": "variant-1",
            "model_id": "model-1",
            "brand_id": "brand-1",
            "format": "glb",
            "url": "https://cdn.example.com/vehicle.glb",
            "version": "1.0.0",
            "storage_key": "configurator/asset-1/v1.0.0/vehicle.glb",
            "storage_status": "VALIDATED",
            "file_size_bytes": 1024,
            "checksum_sha256": "a" * 64,
            "provenance": "AUTO_AI_LICENSED",
            "provenance_evidence": [{
                "evidence_id": "evidence-1",
                "evidence_type": AssetEvidenceType.LICENSE_RECORD.value,
                "status": AssetEvidenceStatus.VERIFIED.value,
                "reference": "LICENSE-1",
                "verified_by": "admin",
                "verified_at": "2026-09-29T00:00:00Z",
            }],
            "license_name": "Verified license",
            "publisher": "Auto AI India",
            "validation_passed": True,
            "admin_reviewed": True,
            "published": False,
            "created_at": "2026-09-29T00:00:00Z",
            "updated_at": "2026-09-29T00:00:00Z",
        }])
        self.configurator_asset_versions = Collection()


def make_client():
    db = DB()
    app = FastAPI()
    app.include_router(make_asset_admin_router(db))

    async def fake_admin():
        return "admin"

    app.dependency_overrides[_require_admin] = fake_admin
    return TestClient(app), db


def test_publish_creates_and_selects_immutable_revision():
    client, db = make_client()
    response = client.post(
        "/api/v1/admin/configurator/assets/publish",
        json={"asset_id": "asset-1", "publish": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["published"] is True
    assert payload["active_revision_id"].startswith("rev-")
    assert len(db.configurator_asset_versions.documents) == 1
    revision = db.configurator_asset_versions.documents[0]
    assert revision["revision_id"] == payload["active_revision_id"]
    assert revision["snapshot_type"] == "PUBLICATION"
    assert revision["published"] is True
    assert revision["storage_status"] == "PUBLISHED"
    assert db.configurator_assets.documents[0]["active_revision_id"] == payload["active_revision_id"]


def test_republishing_matching_active_revision_is_idempotent():
    client, db = make_client()

    first = client.post(
        "/api/v1/admin/configurator/assets/publish",
        json={"asset_id": "asset-1", "publish": True},
    )
    assert first.status_code == 200
    first_revision_id = first.json()["active_revision_id"]

    second = client.post(
        "/api/v1/admin/configurator/assets/publish",
        json={"asset_id": "asset-1", "publish": True},
    )

    assert second.status_code == 200
    assert second.json()["active_revision_id"] == first_revision_id
    assert len(db.configurator_asset_versions.documents) == 1


def test_publish_rejects_asset_without_verified_binary():
    client, db = make_client()
    db.configurator_assets.documents[0]["checksum_sha256"] = None

    response = client.post(
        "/api/v1/admin/configurator/assets/publish",
        json={"asset_id": "asset-1", "publish": True},
    )

    assert response.status_code == 422
    assert db.configurator_asset_versions.documents == []
