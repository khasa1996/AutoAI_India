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


def _validate_structural_references(document: Dict[str, Any]) -> None:
    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    cameras = document.get("cameras", [])
    accessors = document.get("accessors", [])
    animations = document.get("animations", [])
    scenes = document.get("scenes", [])

    for node_index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"GLTF node {node_index} must be an object")
        if "mesh" in node:
            _require_index(node["mesh"], len(meshes), "node mesh")
        if "camera" in node:
            _require_index(node["camera"], len(cameras), "node camera")
        children = node.get("children", [])
        if not isinstance(children, list):
            raise ValueError(f"GLTF node {node_index} children must be an array")
        for child in children:
            _require_index(child, len(nodes), "node child")

    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(f"GLTF scene {scene_index} must be an object")
        scene_nodes = scene.get("nodes", [])
        if not isinstance(scene_nodes, list):
            raise ValueError(f"GLTF scene {scene_index} nodes must be an array")
        for node in scene_nodes:
            _require_index(node, len(nodes), "scene node")

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
