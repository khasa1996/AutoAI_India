"""TDD contract for immutable Ultra 3D asset revision lifecycle."""

import pytest
from pydantic import ValidationError

from configurator_asset_revision import (
    AssetRevisionStatus,
    ConfiguratorAssetRevision,
    can_transition_revision,
    select_active_revision,
)


def _revision(**overrides: object) -> ConfiguratorAssetRevision:
    values = {
        "revision_id": "rev-1",
        "asset_id": "asset-1",
        "variant_id": "variant-1",
        "version": "1.0.0",
        "checksum_sha256": "a" * 64,
        "state": "INTAKE",
        "supersedes_revision_id": None,
    }
    values.update(overrides)
    return ConfiguratorAssetRevision(**values)


def test_revision_identity_requires_stable_identity_fields() -> None:
    with pytest.raises(ValidationError):
        _revision(revision_id="")

    with pytest.raises(ValidationError):
        _revision(checksum_sha256="bad")


def test_revision_evidence_is_immutable_after_validation() -> None:
    revision = _revision()
    with pytest.raises(ValidationError):
        revision.version = "2.0.0"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("INTAKE", "VALIDATING"),
        ("VALIDATING", "VALIDATED"),
        ("VALIDATED", "REVIEWED"),
        ("REVIEWED", "PUBLISHED"),
        ("PUBLISHED", "SUPERSEDED"),
    ],
)
def test_revision_lifecycle_allows_only_forward_publication_transitions(
    current: str,
    target: str,
) -> None:
    assert can_transition_revision(
        AssetRevisionStatus(current),
        AssetRevisionStatus(target),
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("INTAKE", "PUBLISHED"),
        ("VALIDATING", "REVIEWED"),
        ("VALIDATED", "PUBLISHED"),
        ("PUBLISHED", "VALIDATED"),
        ("SUPERSEDED", "PUBLISHED"),
    ],
)
def test_revision_lifecycle_blocks_invalid_transitions(
    current: str,
    target: str,
) -> None:
    assert not can_transition_revision(
        AssetRevisionStatus(current),
        AssetRevisionStatus(target),
    )


def test_active_revision_selection_requires_published_revision_and_matching_variant() -> None:
    revisions = [
        _revision(revision_id="rev-old", version="1.0.0", state="PUBLISHED"),
        _revision(
            revision_id="rev-new",
            version="2.0.0",
            checksum_sha256="b" * 64,
            state="REVIEWED",
            supersedes_revision_id="rev-old",
        ),
    ]

    assert select_active_revision("rev-old", revisions).revision_id == "rev-old"

    with pytest.raises(ValueError, match="active revision must be PUBLISHED"):
        select_active_revision("rev-new", revisions)


def test_active_revision_selection_rejects_cross_variant_revision() -> None:
    revisions = [
        _revision(
            revision_id="rev-other",
            variant_id="variant-2",
            state="PUBLISHED",
        ),
    ]

    with pytest.raises(ValueError, match="does not match"):
        select_active_revision("rev-other", revisions, expected_variant_id="variant-1")


def test_authoritative_revision_resolution_rejects_duplicate_revision_ids() -> None:
    from configurator_asset_revision import resolve_authoritative_asset_revision

    asset = {
        "asset_id": "asset-1",
        "variant_id": "variant-1",
        "active_revision_id": "rev-1",
    }
    revisions = [
        _revision(revision_id="rev-1", state="PUBLISHED"),
        _revision(revision_id="rev-1", version="2.0.0", checksum_sha256="b" * 64, state="PUBLISHED"),
    ]

    with pytest.raises(ValueError, match="duplicate revision IDs"):
        resolve_authoritative_asset_revision(asset, revisions)
