import json
import struct

import pytest

from configurator_asset_inspection import inspect_gltf_bytes


def make_glb(gltf):
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_padding = (-len(json_bytes)) % 4
    json_bytes += b" " * json_padding
    total_length = 12 + 8 + len(json_bytes)
    return b"glTF" + struct.pack("<II", 2, total_length) + struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes


def test_inspection_extracts_mesh_material_animation_and_camera_names():
    payload = make_glb(
        {
            "asset": {"version": "2.0"},
            "nodes": [
                {"name": "Body"},
                {"name": "Wheel_FL", "mesh": 0},
                {"name": "Wheel_FR", "mesh": 0},
            ],
            "meshes": [{"name": "WheelMesh", "primitives": [{"attributes": {"POSITION": 0}}]}],
            "accessors": [{"count": 1, "componentType": 5126, "type": "VEC3"}],
            "materials": [{"name": "BODY_PAINT"}, {"name": "INTERIOR"}],
            "animations": [{"name": "OpenDoors"}, {"name": "OpenSunroof"}],
            "cameras": [{"name": "Exterior_Front"}, {"name": "Interior_Driver"}],
        }
    )

    result = inspect_gltf_bytes(payload, filename="car.glb")

    assert result["format"] == "glb"
    assert result["version"] == 2
    assert result["mesh_names"] == ["WheelMesh"]
    assert result["node_names"] == ["Body", "Wheel_FL", "Wheel_FR"]
    assert result["material_names"] == ["BODY_PAINT", "INTERIOR"]
    assert result["animation_names"] == ["OpenDoors", "OpenSunroof"]
    assert result["camera_names"] == ["Exterior_Front", "Interior_Driver"]


def test_inspection_rejects_invalid_glb_header():
    with pytest.raises(ValueError, match="valid GLB"):
        inspect_gltf_bytes(b"not-a-glb", filename="car.glb")


def test_inspection_rejects_gltf_version_other_than_two():
    payload = b"glTF" + struct.pack("<II", 1, 12)
    with pytest.raises(ValueError, match="version 2"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_json_with_duplicate_named_meshes():
    payload = make_glb(
        {
            "asset": {"version": "2.0"},
            "meshes": [
                {"name": "Body", "primitives": [{"attributes": {}}]},
                {"name": "Body", "primitives": [{"attributes": {}}]},
            ],
        }
    )

    with pytest.raises(ValueError, match="duplicate mesh"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_node_mesh_reference_out_of_range():
    payload = make_glb({"asset": {"version": "2.0"}, "nodes": [{"name": "Body", "mesh": 2}], "meshes": [{"name": "BodyMesh"}]})
    with pytest.raises(ValueError, match="node mesh index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_node_camera_reference_out_of_range():
    payload = make_glb({"asset": {"version": "2.0"}, "nodes": [{"name": "Camera", "camera": 1}], "cameras": [{"name": "Exterior"}]})
    with pytest.raises(ValueError, match="node camera index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_node_child_reference_out_of_range():
    payload = make_glb({"asset": {"version": "2.0"}, "nodes": [{"name": "Body", "children": [1]}]})
    with pytest.raises(ValueError, match="node child index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_animation_channel_node_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "nodes": [{"name": "Body"}],
        "animations": [{"name": "OpenDoor", "samplers": [{"input": 0, "output": 1}], "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}]}],
        "accessors": [{"count": 1, "componentType": 5126, "type": "SCALAR"}, {"count": 1, "componentType": 5126, "type": "VEC4"}],
    })
    with pytest.raises(ValueError, match="animation channel target node index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_mesh_primitive_accessor_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "meshes": [{"name": "Body", "primitives": [{"attributes": {"POSITION": 2}}]}],
        "accessors": [{"count": 1, "componentType": 5126, "type": "VEC3"}],
    })
    with pytest.raises(ValueError, match="mesh primitive POSITION accessor index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_mesh_primitive_material_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "meshes": [{"name": "Body", "primitives": [{"attributes": {}, "material": 1}]}],
        "materials": [{"name": "BodyPaint"}],
    })
    with pytest.raises(ValueError, match="mesh primitive material index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_skin_joint_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "nodes": [{"name": "Body"}],
        "skins": [{"name": "BodyRig", "joints": [1]}],
    })
    with pytest.raises(ValueError, match="skin joint index"):
        inspect_gltf_bytes(payload, filename="car.glb")



def test_inspection_rejects_buffer_view_that_exceeds_buffer_length():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "bufferViews": [{"buffer": 0, "byteOffset": 8, "byteLength": 8}],
        "buffers": [{"byteLength": 12}],
    })

    with pytest.raises(ValueError, match="exceeds buffer byteLength"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_accessor_buffer_view_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "accessors": [{"count": 1, "componentType": 5126, "type": "VEC3", "bufferView": 1}],
        "bufferViews": [{"buffer": 0, "byteLength": 12}],
        "buffers": [{"byteLength": 12}],
    })

    with pytest.raises(ValueError, match="accessor bufferView index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_buffer_view_buffer_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "bufferViews": [{"buffer": 1, "byteLength": 12}],
        "buffers": [{"byteLength": 12}],
    })

    with pytest.raises(ValueError, match="bufferView buffer index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_sparse_accessor_references():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "accessors": [{
            "count": 2,
            "componentType": 5126,
            "type": "VEC3",
            "sparse": {
                "count": 1,
                "indices": {"bufferView": 2, "componentType": 5123},
                "values": {"bufferView": 0},
            },
        }],
        "bufferViews": [{"buffer": 0, "byteLength": 12}],
        "buffers": [{"byteLength": 12}],
    })

    with pytest.raises(ValueError, match="sparse indices bufferView index"):
        inspect_gltf_bytes(payload, filename="car.glb")


def test_inspection_rejects_invalid_buffer_view_stride():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "bufferViews": [{"buffer": 0, "byteLength": 12, "byteStride": 3}],
        "buffers": [{"byteLength": 12}],
    })

    with pytest.raises(ValueError, match="bufferView byteStride"):
        inspect_gltf_bytes(payload, filename="car.glb")

def test_inspection_rejects_default_scene_reference_out_of_range():
    payload = make_glb({
        "asset": {"version": "2.0"},
        "scene": 1,
        "scenes": [{"name": "Scene"}],
    })
    with pytest.raises(ValueError, match="default scene index"):
        inspect_gltf_bytes(payload, filename="car.glb")
