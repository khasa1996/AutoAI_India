import pytest

from configurator_asset_revision import AssetRevisionStatus, ConfiguratorAssetRevision
from configurator_runtime_capabilities import resolve_authoritative_asset_revision


def _revision(
    revision_id: str = "rev-1",
    variant_id: str = "demo-variant",
    state: AssetRevisionStatus = AssetRevisionStatus.PUBLISHED,
) -> ConfiguratorAssetRevision:
    return ConfiguratorAssetRevision(
        revision_id=revision_id,
        asset_id="asset-1",
        variant_id=variant_id,
        version="1.0.0",
        checksum_sha256="a" * 64,
        state=state,
    )


def _asset(**overrides: object) -> dict[str, object]:
    asset: dict[str, object] = {
        "asset_id": "asset-1",
        "variant_id": "demo-variant",
        "active_revision_id": "rev-1",
    }
    asset.update(overrides)
    return asset


def test_runtime_resolves_only_the_asset_active_revision() -> None:
    asset = _asset()
    revisions = [
        _revision("rev-old", state=AssetRevisionStatus.SUPERSEDED),
        _revision("rev-1", state=AssetRevisionStatus.PUBLISHED),
    ]

    selected = resolve_authoritative_asset_revision(asset, revisions)

    assert selected.revision_id == "rev-1"


@pytest.mark.parametrize(
    "state",
    [
        AssetRevisionStatus.INTAKE,
        AssetRevisionStatus.VALIDATING,
        AssetRevisionStatus.VALIDATED,
        AssetRevisionStatus.REVIEWED,
        AssetRevisionStatus.SUPERSEDED,
    ],
)
def test_runtime_rejects_non_published_active_revision(
    state: AssetRevisionStatus,
) -> None:
    asset = _asset()
    revisions = [_revision(state=state)]

    with pytest.raises(ValueError, match="active revision must be PUBLISHED"):
        resolve_authoritative_asset_revision(asset, revisions)


def test_runtime_rejects_missing_active_revision() -> None:
    asset = _asset(active_revision_id="rev-missing")

    with pytest.raises(ValueError, match="active revision was not found"):
        resolve_authoritative_asset_revision(asset, [_revision()])


def test_runtime_rejects_cross_variant_active_revision() -> None:
    asset = _asset()
    revisions = [_revision(variant_id="other-variant")]

    with pytest.raises(ValueError, match="does not match expected variant"):
        resolve_authoritative_asset_revision(asset, revisions)


def test_runtime_rejects_revision_for_a_different_asset() -> None:
    asset = _asset()
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


def test_runtime_requires_active_revision_identity() -> None:
    asset = _asset(active_revision_id=None)

    with pytest.raises(ValueError, match="active revision is not configured"):
        resolve_authoritative_asset_revision(asset, [_revision()])
