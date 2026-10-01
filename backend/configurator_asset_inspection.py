"""Inspect GLB/GLTF structure without trusting client-supplied asset metadata."""

from __future__ import annotations

import json
import struct
from typing import Any, Dict, List, Optional

_GLB_MAGIC = b"glTF"
_GLB_VERSION = 2
_JSON_CHUNK_TYPE = 0x4E4F534A
_HEADER_SIZE = 12
_CHUNK_HEADER_SIZE = 8


def _unique_names(items: List[Dict[str, Any]], kind: str) -> List[str]:
    names = [str(item["name"]) for item in items if isinstance(item, dict) and str(item.get("name", "")).strip()]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate {kind} name")
    return names


def _read_glb_json(payload: bytes) -> Dict[str, Any]:
    if len(payload) < _HEADER_SIZE or payload[:4] != _GLB_MAGIC:
        raise ValueError("Not a valid GLB file")

    version, declared_length = struct.unpack_from("<II", payload, 4)
    if version != _GLB_VERSION:
        raise ValueError("GLB version 2 is required")
    if declared_length != len(payload):
        raise ValueError("GLB declared length does not match payload length")

    offset = _HEADER_SIZE
    while offset + _CHUNK_HEADER_SIZE <= len(payload):
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        offset += _CHUNK_HEADER_SIZE
        end = offset + chunk_length
        if end > len(payload):
            raise ValueError("GLB chunk extends beyond payload")
        chunk = payload[offset:end]
        offset = end
        if chunk_type == _JSON_CHUNK_TYPE:
            try:
                document = json.loads(chunk.rstrip(b" \t\r\n").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("GLB JSON chunk is invalid") from exc
            if not isinstance(document, dict):
                raise ValueError("GLB JSON root must be an object")
            return document

    raise ValueError("GLB does not contain a JSON chunk")


def _require_index(value: Any, limit: int, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= limit:
        raise ValueError(f"{label} index is out of range")


def _require_non_negative_integer(value: Any, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")


def _validate_structural_references(document: Dict[str, Any]) -> None:
    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    cameras = document.get("cameras", [])
    accessors = document.get("accessors", [])
    animations = document.get("animations", [])
    scenes = document.get("scenes", [])
    skins = document.get("skins", [])
    buffer_views = document.get("bufferViews", [])
    buffers = document.get("buffers", [])

    for collection, kind in (
        (buffer_views, "bufferViews"),
        (buffers, "buffers"),
    ):
        if not isinstance(collection, list):
            raise ValueError(f"GLTF {kind} must be an array")

    for buffer_view_index, buffer_view in enumerate(buffer_views):
        if not isinstance(buffer_view, dict):
            raise ValueError(f"GLTF bufferView {buffer_view_index} must be an object")
        if "buffer" not in buffer_view:
            raise ValueError(f"GLTF bufferView {buffer_view_index} buffer is required")
        _require_index(buffer_view["buffer"], len(buffers), "bufferView buffer")
        if "byteOffset" in buffer_view:
            _require_non_negative_integer(buffer_view["byteOffset"], "bufferView byteOffset")
        if "byteLength" not in buffer_view:
            raise ValueError(f"GLTF bufferView {buffer_view_index} byteLength is required")
        _require_non_negative_integer(buffer_view["byteLength"], "bufferView byteLength")
        buffer = buffers[buffer_view["buffer"]]
        buffer_end = buffer_view.get("byteOffset", 0) + buffer_view["byteLength"]
        if buffer_end > buffer["byteLength"]:
            raise ValueError(f"GLTF bufferView {buffer_view_index} exceeds buffer byteLength")
        if "byteStride" in buffer_view:
            stride = buffer_view["byteStride"]
            if not isinstance(stride, int) or isinstance(stride, bool) or stride < 4 or stride > 252 or stride % 4:
                raise ValueError("bufferView byteStride is invalid")

    for buffer_index, buffer in enumerate(buffers):
        if not isinstance(buffer, dict):
            raise ValueError(f"GLTF buffer {buffer_index} must be an object")
        if "byteLength" not in buffer:
            raise ValueError(f"GLTF buffer {buffer_index} byteLength is required")
        _require_non_negative_integer(buffer["byteLength"], "buffer byteLength")

    for accessor_index, accessor in enumerate(accessors):
        if not isinstance(accessor, dict):
            raise ValueError(f"GLTF accessor {accessor_index} must be an object")
        if "bufferView" in accessor:
            _require_index(accessor["bufferView"], len(buffer_views), "accessor bufferView")
        if "byteOffset" in accessor:
            _require_non_negative_integer(accessor["byteOffset"], "accessor byteOffset")
        if "count" not in accessor:
            raise ValueError(f"GLTF accessor {accessor_index} count is required")
        _require_non_negative_integer(accessor["count"], "accessor count")
        if "componentType" in accessor:
            if accessor["componentType"] not in {5120, 5121, 5122, 5123, 5125, 5126}:
                raise ValueError("accessor componentType is invalid")
        if "type" in accessor:
            if accessor["type"] not in {"SCALAR", "VEC2", "VEC3", "VEC4", "MAT2", "MAT3", "MAT4"}:
                raise ValueError("accessor type is invalid")
        sparse = accessor.get("sparse")
        if sparse is not None:
            if not isinstance(sparse, dict):
                raise ValueError(f"GLTF accessor {accessor_index} sparse must be an object")
            if "count" not in sparse:
                raise ValueError(f"GLTF accessor {accessor_index} sparse count is required")
            _require_non_negative_integer(sparse["count"], "accessor sparse count")
            indices = sparse.get("indices")
            values = sparse.get("values")
            if not isinstance(indices, dict) or not isinstance(values, dict):
                raise ValueError(f"GLTF accessor {accessor_index} sparse indices and values are required")
            if "bufferView" not in indices or "bufferView" not in values:
                raise ValueError(f"GLTF accessor {accessor_index} sparse bufferView is required")
            _require_index(indices["bufferView"], len(buffer_views), "sparse indices bufferView")
            _require_index(values["bufferView"], len(buffer_views), "sparse values bufferView")
            if "byteOffset" in indices:
                _require_non_negative_integer(indices["byteOffset"], "sparse indices byteOffset")
            if "byteOffset" in values:
                _require_non_negative_integer(values["byteOffset"], "sparse values byteOffset")
            if "componentType" not in indices or indices["componentType"] not in {5121, 5123, 5125}:
                raise ValueError("sparse indices componentType is invalid")

    for node_index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"GLTF node {node_index} must be an object")
        if "mesh" in node:
            _require_index(node["mesh"], len(meshes), "node mesh")
        if "camera" in node:
            _require_index(node["camera"], len(cameras), "node camera")
        if "skin" in node:
            _require_index(node["skin"], len(skins), "node skin")
        children = node.get("children", [])
        if not isinstance(children, list):
            raise ValueError(f"GLTF node {node_index} children must be an array")
        for child in children:
            _require_index(child, len(nodes), "node child")

    for mesh_index, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            raise ValueError(f"GLTF mesh {mesh_index} must be an object")
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list) or not primitives:
            raise ValueError(f"GLTF mesh {mesh_index} primitives must be a non-empty array")
        for primitive_index, primitive in enumerate(primitives):
            if not isinstance(primitive, dict):
                raise ValueError(f"GLTF mesh primitive {mesh_index}:{primitive_index} must be an object")
            attributes = primitive.get("attributes", {})
            if not isinstance(attributes, dict):
                raise ValueError(f"GLTF mesh primitive {mesh_index}:{primitive_index} attributes must be an object")
            for attribute, accessor in attributes.items():
                _require_index(accessor, len(accessors), f"mesh primitive {attribute} accessor")
            for field in ("indices", "material"):
                if field in primitive:
                    limit = len(accessors) if field == "indices" else len(document.get("materials", []))
                    _require_index(primitive[field], limit, f"mesh primitive {field}")
            targets = primitive.get("targets", [])
            if not isinstance(targets, list):
                raise ValueError(f"GLTF mesh primitive {mesh_index}:{primitive_index} targets must be an array")
            for target_index, target in enumerate(targets):
                if not isinstance(target, dict):
                    raise ValueError(f"GLTF mesh primitive target {mesh_index}:{primitive_index}:{target_index} must be an object")
                for attribute, accessor in target.items():
                    _require_index(accessor, len(accessors), f"mesh primitive target {attribute} accessor")

    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"GLTF scene {scene_index} must be an object")
        scene_nodes = scene.get("nodes", [])
        if not isinstance(scene_nodes, list):
            raise ValueError(f"GLTF scene {scene_index} nodes must be an array")
        for node in scene_nodes:
            _require_index(node, len(nodes), "scene node")

    if "scene" in document:
        _require_index(document["scene"], len(scenes), "default scene")

    for skin_index, skin in enumerate(skins):
        if not isinstance(skin, dict):
            raise ValueError(f"GLTF skin {skin_index} must be an object")
        joints = skin.get("joints")
        if not isinstance(joints, list) or not joints:
            raise ValueError(f"GLTF skin {skin_index} joints must be a non-empty array")
        for joint in joints:
            _require_index(joint, len(nodes), "skin joint")
        for field in ("skeleton", "inverseBindMatrices"):
            if field in skin:
                limit = len(nodes) if field == "skeleton" else len(accessors)
                _require_index(skin[field], limit, f"skin {field}")

    for animation_index, animation in enumerate(animations):
        if not isinstance(animation, dict):
            raise ValueError(f"GLTF animation {animation_index} must be an object")
        samplers = animation.get("samplers", [])
        channels = animation.get("channels", [])
        if not isinstance(samplers, list) or not isinstance(channels, list):
            raise ValueError(f"GLTF animation {animation_index} samplers and channels must be arrays")
        for sampler_index, sampler in enumerate(samplers):
            if not isinstance(sampler, dict):
                raise ValueError(f"GLTF animation sampler {sampler_index} must be an object")
            if "input" in sampler:
                _require_index(sampler["input"], len(accessors), "animation sampler input")
            if "output" in sampler:
                _require_index(sampler["output"], len(accessors), "animation sampler output")
        for channel_index, channel in enumerate(channels):
            if not isinstance(channel, dict):
                raise ValueError(f"GLTF animation channel {channel_index} must be an object")
            if "sampler" not in channel:
                raise ValueError(f"GLTF animation channel {channel_index} sampler is required")
            _require_index(channel["sampler"], len(samplers), "animation channel sampler")
            target = channel.get("target")
            if not isinstance(target, dict):
                raise ValueError(f"GLTF animation channel {channel_index} target must be an object")
            if "node" in target:
                _require_index(target["node"], len(nodes), "animation channel target node")


def inspect_gltf_bytes(payload: bytes, filename: Optional[str] = None) -> Dict[str, Any]:
    """Return deterministic structural metadata from a GLB payload."""
    if not isinstance(payload, bytes):
        raise TypeError("GLB payload must be bytes")
    if filename and filename.lower().endswith(".gltf"):
        raise ValueError("Binary inspection requires a GLB payload")

    document = _read_glb_json(payload)
    asset = document.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        raise ValueError("GLTF asset version 2.0 is required")

    meshes = document.get("meshes", [])
    materials = document.get("materials", [])
    nodes = document.get("nodes", [])
    animations = document.get("animations", [])
    cameras = document.get("cameras", [])
    for collection, kind in (
        (meshes, "meshes"),
        (materials, "materials"),
        (nodes, "nodes"),
        (animations, "animations"),
        (cameras, "cameras"),
    ):
        if not isinstance(collection, list):
            raise ValueError(f"GLTF {kind} must be an array")

    _validate_structural_references(document)

    return {
        "format": "glb",
        "version": 2,
        "mesh_names": _unique_names(meshes, "mesh"),
        "node_names": _unique_names(nodes, "node"),
        "material_names": _unique_names(materials, "material"),
        "animation_names": _unique_names(animations, "animation"),
        "camera_names": _unique_names(cameras, "camera"),
        "mesh_count": len(meshes),
        "material_count": len(materials),
        "node_count": len(nodes),
        "animation_count": len(animations),
        "camera_count": len(cameras),
    }
