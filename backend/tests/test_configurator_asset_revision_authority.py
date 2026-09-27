import pytest

from configurator_asset_revision import (
    AssetRevisionStatus,
    ConfiguratorAssetRevision,
    resolve_authoritative_asset_revision,
)


def _revision() -> ConfiguratorAssetRevision:
    return ConfiguratorAssetRevision(
        revision_id="rev-1",
        asset_id="asset-1",
        variant_id="demo-variant",
        version="1.0.0",
        checksum_sha256="a" * 64,
        state=AssetRevisionStatus.PUBLISHED,
    )


def test_asset_revision_module_exposes_authoritative_resolution() -> None:
    asset = {
        "asset_id": "asset-1",
        "variant_id": "demo-variant",
        "active_revision_id": "rev-1",
    }

    selected = resolve_authoritative_asset_revision(asset, [_revision()])

    assert selected.revision_id == "rev-1"


def test_asset_revision_module_rejects_revision_for_a_different_asset() -> None:
    asset = {
        "asset_id": "asset-1",
        "variant_id": "demo-variant",
        "active_revision_id": "rev-1",
    }
    revision = ConfiguratorAssetRevision(
        revision_id="rev-1",
        asset_id="asset-2",
        variant_id="demo-variant",
        version="1.0.0",
        checksum_sha256="a" * 64,
        state=AssetRevisionStatus.PUBLISHED,
    )

    with pytest.raises(ValueError, match="does not belong to asset"):
        resolve_authoritative_asset_revision(asset, [revision])
