"""Validation rules for publishable Auto AI India 3D asset manifests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from configurator_schemas import AssetProvenance, ConfiguratorAssetCreate

_ALLOWED_INTERACTIONS = {
    "doors",
    "hood",
    "boot",
    "frunk",
    "sunroof",
    "headlights",
    "drl",
    "taillights",
    "fog_lights",
    "left_indicator",
    "right_indicator",
    "hazard",
    "interior_lights",
    "camera_exterior",
    "camera_interior",
}


def validate_asset_manifest(
    asset: ConfiguratorAssetCreate,
    mesh_names: Iterable[str],
    material_names: Iterable[str] = (),
    inspected_camera_preset_names: Optional[Iterable[str]] = None,
    inspected_animation_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Validate metadata and exact mesh/material/interaction mappings before publication."""
    errors: List[str] = []
    warnings: List[str] = []
    available_meshes = {str(name) for name in mesh_names if str(name).strip()}
    available_materials = {str(name) for name in material_names if str(name).strip()}
    available_cameras = (
        {str(name) for name in inspected_camera_preset_names if str(name).strip()}
        if inspected_camera_preset_names is not None
        else None
    )
    available_animations = (
        {str(name) for name in inspected_animation_names if str(name).strip()}
        if inspected_animation_names is not None
        else None
    )

    if not asset.is_publishable():
        errors.append("Asset is not publishable: provenance, verified evidence, validation, admin review, license and publisher are all required")
    if asset.provenance == AssetProvenance.AI_GENERATED_CONCEPT:
        errors.append("AI-generated concept assets cannot be published as production vehicle assets")

    unknown_interactions = sorted(set(asset.supported_interactions) - _ALLOWED_INTERACTIONS)
    if unknown_interactions:
        errors.append("Unsupported interaction names: " + ", ".join(unknown_interactions))

    for option_id, mesh_name in asset.wheel_mesh_names.items():
        if mesh_name not in available_meshes:
            errors.append(f"Wheel mapping '{option_id}' references missing mesh '{mesh_name}'")

    for option_id, mapped_meshes in asset.option_mesh_names.items():
        if not mapped_meshes:
            errors.append(f"Option mapping '{option_id}' must contain at least one mesh")
            continue
        missing = [mesh for mesh in mapped_meshes if mesh not in available_meshes]
        if missing:
            errors.append(f"Option mapping '{option_id}' references missing meshes: {', '.join(missing)}")

    for material_name in asset.paint_material_names:
        if material_name not in available_materials:
            if available_materials:
                errors.append(f"Paint material '{material_name}' is not present in the inspected asset")
            else:
                warnings.append(f"Paint material '{material_name}' could not be cross-checked because no inspected material names were supplied")

    for interior_id, mapped_materials in asset.interior_material_mappings.items():
        if not mapped_materials:
            errors.append(f"Interior material mapping '{interior_id}' must contain at least one material")
            continue
        if not available_materials:
            warnings.append(f"Interior material mapping '{interior_id}' could not be cross-checked because no inspected material names were supplied")
            continue
        missing = [material for material in mapped_materials if material not in available_materials]
        if missing:
            errors.append(
                f"Interior material mapping '{interior_id}' references missing materials: {', '.join(missing)}"
            )

    if available_cameras is not None:
        missing_cameras = [name for name in asset.camera_preset_names if name not in available_cameras]
        if missing_cameras:
            errors.append("Camera preset mapping references missing cameras: " + ", ".join(missing_cameras))
    elif asset.camera_preset_names:
        warnings.append("Camera presets could not be cross-checked because no inspected camera names were supplied")

    for interaction, mappings in asset.interaction_animation_names.items():
        if interaction not in asset.supported_interactions:
            errors.append(f"Animation mapping '{interaction}' requires an unsupported interaction")
            continue
        if not mappings:
            errors.append(f"Animation mapping '{interaction}' must contain at least one animation name")
            continue
        animation_names = [name for name in mappings.values() if str(name).strip()]
        if len(animation_names) != len(mappings):
            errors.append(f"Animation mapping '{interaction}' contains an empty animation name")
            continue
        if available_animations is None:
            warnings.append(f"Animation mapping '{interaction}' could not be cross-checked because no inspected animation names were supplied")
            continue
        missing = [name for name in animation_names if name not in available_animations]
        if missing:
            errors.append(f"Animation mapping '{interaction}' references missing animations: {', '.join(missing)}")

    duplicate_meshes = [
        mesh for mesh in available_meshes
        if sum(mesh in values for values in asset.wheel_mesh_names.values())
        + sum(mesh in meshes for meshes in asset.option_mesh_names.values()) > 1
    ]
    if duplicate_meshes:
        warnings.append("Some optional mappings share mesh names; verify that this is intentional")

    return {"valid": not errors, "errors": errors, "warnings": warnings}
