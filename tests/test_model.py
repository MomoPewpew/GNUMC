"""Tests for model.py — geometry, UV mapping, poses."""

import math
import pytest

from model import (
    _box_uvs, BoxPart, SteveModel, AlexModel,
    get_transformed_quads, _rotate_point, TEX_W, TEX_H,
)


# ---------------------------------------------------------------------------
# _box_uvs
# ---------------------------------------------------------------------------

class TestBoxUVs:
    def test_head_uvs_front(self):
        """Head: origin (0,0), size 8x8x8.  Front = (8,8)-(16,16) in pixels."""
        uvs = _box_uvs(0, 0, 8, 8, 8)
        assert uvs["front"] == pytest.approx((8/64, 8/64, 16/64, 16/64))

    def test_head_uvs_right(self):
        uvs = _box_uvs(0, 0, 8, 8, 8)
        assert uvs["right"] == pytest.approx((0/64, 8/64, 8/64, 16/64))

    def test_head_uvs_top(self):
        uvs = _box_uvs(0, 0, 8, 8, 8)
        assert uvs["top"] == pytest.approx((8/64, 0/64, 16/64, 8/64))

    def test_head_uvs_bottom(self):
        uvs = _box_uvs(0, 0, 8, 8, 8)
        assert uvs["bottom"] == pytest.approx((16/64, 0/64, 24/64, 8/64))

    def test_body_uvs_front(self):
        """Body: origin (16,16), size 8x12x4."""
        uvs = _box_uvs(16, 16, 8, 12, 4)
        assert uvs["front"] == pytest.approx((20/64, 20/64, 28/64, 32/64))

    def test_body_uvs_right(self):
        uvs = _box_uvs(16, 16, 8, 12, 4)
        assert uvs["right"] == pytest.approx((16/64, 20/64, 20/64, 32/64))

    def test_slim_arm_front_narrower_than_classic(self):
        steve = _box_uvs(40, 16, 4, 12, 4)
        alex = _box_uvs(40, 16, 3, 12, 4)
        steve_w = steve["front"][2] - steve["front"][0]
        alex_w = alex["front"][2] - alex["front"][0]
        assert alex_w < steve_w
        assert alex_w == pytest.approx(3 / 64)
        assert steve_w == pytest.approx(4 / 64)

    def test_slim_arm_top_narrower_than_classic(self):
        steve = _box_uvs(40, 16, 4, 12, 4)
        alex = _box_uvs(40, 16, 3, 12, 4)
        steve_w = steve["top"][2] - steve["top"][0]
        alex_w = alex["top"][2] - alex["top"][0]
        assert alex_w == pytest.approx(3 / 64)
        assert steve_w == pytest.approx(4 / 64)

    def test_side_faces_depth_unchanged_for_slim(self):
        """Right/left face width is determined by depth, not arm width."""
        steve = _box_uvs(40, 16, 4, 12, 4)
        alex = _box_uvs(40, 16, 3, 12, 4)
        assert (steve["right"][2] - steve["right"][0] ==
                pytest.approx(alex["right"][2] - alex["right"][0]))

    def test_all_uvs_in_unit_range(self):
        for u0, v0, w, h, d in [(0,0,8,8,8), (16,16,8,12,4), (40,16,3,12,4)]:
            uvs = _box_uvs(u0, v0, w, h, d)
            for face, (a, b, c, e) in uvs.items():
                assert 0 <= a <= 1 and 0 <= b <= 1, f"{face}"
                assert 0 <= c <= 1 and 0 <= e <= 1, f"{face}"
                assert c > a and e > b, f"{face} inverted"

    def test_six_faces_returned(self):
        uvs = _box_uvs(0, 0, 4, 4, 4)
        assert set(uvs.keys()) == {"front", "back", "left", "right", "top", "bottom"}


# ---------------------------------------------------------------------------
# BoxPart
# ---------------------------------------------------------------------------

class TestBoxPart:
    def test_six_face_quads(self):
        part = BoxPart("test", (0, 0, 0), (2, 3, 4), (0, 0))
        assert len(part.get_face_quads()) == 6

    def test_four_vertices_per_face(self):
        part = BoxPart("test", (0, 0, 0), (4, 4, 4), (0, 0))
        for name, verts, uvs in part.get_face_quads():
            assert len(verts) == 4
            assert len(uvs) == 4
            for v in verts:
                assert len(v) == 3
            for uv in uvs:
                assert len(uv) == 2

    def test_inflate_expands_size(self):
        base = BoxPart("b", (0, 0, 0), (4, 4, 4), (0, 0), inflate=0)
        infl = BoxPart("i", (0, 0, 0), (4, 4, 4), (0, 0), inflate=0.5)
        for i in range(3):
            assert infl.size[i] == pytest.approx(base.size[i] + 1.0)

    def test_inflate_shifts_origin(self):
        base = BoxPart("b", (2, 3, 4), (4, 4, 4), (0, 0), inflate=0)
        infl = BoxPart("i", (2, 3, 4), (4, 4, 4), (0, 0), inflate=0.5)
        for i in range(3):
            assert infl.origin[i] == pytest.approx(base.origin[i] - 0.5)

    def test_face_names(self):
        part = BoxPart("test", (0, 0, 0), (4, 4, 4), (0, 0))
        names = {n for n, _, _ in part.get_face_quads()}
        assert names == {"front", "back", "left", "right", "top", "bottom"}


# ---------------------------------------------------------------------------
# SteveModel / AlexModel
# ---------------------------------------------------------------------------

class TestSteveModel:
    def test_six_base_parts(self):
        assert len(SteveModel().base_parts) == 6

    def test_six_overlay_parts(self):
        assert len(SteveModel().overlay_parts) == 6

    def test_arm_width_is_4(self):
        for p in SteveModel().base_parts:
            if "Arm" in p.name:
                assert p.size[0] == 4, f"{p.name}"

    def test_overlay_arm_width_is_4(self):
        for p in SteveModel().overlay_parts:
            if "Sleeve" in p.name:
                assert p.size[0] == pytest.approx(4 + 2 * 0.5)

    def test_base_part_names(self):
        names = {p.name for p in SteveModel().base_parts}
        assert names == {"head", "body", "rightArm", "leftArm", "rightLeg", "leftLeg"}


class TestAlexModel:
    def test_six_base_parts(self):
        assert len(AlexModel().base_parts) == 6

    def test_six_overlay_parts(self):
        assert len(AlexModel().overlay_parts) == 6

    def test_arm_width_is_3(self):
        for p in AlexModel().base_parts:
            if "Arm" in p.name:
                assert p.size[0] == 3, f"{p.name}"

    def test_overlay_arm_width_is_3_plus_inflate(self):
        for p in AlexModel().overlay_parts:
            if "Sleeve" in p.name:
                assert p.size[0] == pytest.approx(3 + 2 * 0.5)

    def test_non_arm_parts_match_steve(self):
        steve = {p.name: p.size for p in SteveModel().base_parts if "Arm" not in p.name}
        alex = {p.name: p.size for p in AlexModel().base_parts if "Arm" not in p.name}
        for name in steve:
            assert steve[name] == alex[name], f"{name} mismatch"

    def test_arm_uv_origins_same_as_steve(self):
        """Alex arms use the same UV origins; only the width param changes the mapping."""
        steve_arms = {p.name: p.uv_origin for p in SteveModel().base_parts if "Arm" in p.name}
        alex_arms = {p.name: p.uv_origin for p in AlexModel().base_parts if "Arm" in p.name}
        for name in steve_arms:
            assert steve_arms[name] == alex_arms[name], f"{name} UV origin mismatch"


# ---------------------------------------------------------------------------
# Poses
# ---------------------------------------------------------------------------

class TestPose:
    def test_standing_no_rotation(self):
        m = SteveModel()
        m.set_pose(0)
        for p in m.get_all_parts():
            assert p.rotation == (0, 0, 0), p.name

    def test_walking_rotates_limbs(self):
        m = SteveModel()
        m.set_pose(1)
        ra = next(p for p in m.base_parts if p.name == "rightArm")
        la = next(p for p in m.base_parts if p.name == "leftArm")
        assert ra.rotation[0] != 0
        assert la.rotation[0] != 0
        assert ra.rotation[0] == -la.rotation[0]

    def test_t_pose_arms_out(self):
        m = SteveModel()
        m.set_pose(2)
        ra = next(p for p in m.base_parts if p.name == "rightArm")
        la = next(p for p in m.base_parts if p.name == "leftArm")
        assert ra.rotation == (0, 0, 90)
        assert la.rotation == (0, 0, -90)

    def test_pose_applies_to_alex(self):
        m = AlexModel()
        m.set_pose(1)
        ra = next(p for p in m.base_parts if p.name == "rightArm")
        assert ra.rotation[0] != 0

    def test_reset_pose(self):
        m = SteveModel()
        m.set_pose(1)
        m.set_pose(0)
        for p in m.get_all_parts():
            assert p.rotation == (0, 0, 0), p.name


# ---------------------------------------------------------------------------
# _rotate_point
# ---------------------------------------------------------------------------

class TestRotatePoint:
    def test_no_rotation(self):
        assert _rotate_point(1, 2, 3, (0, 0, 0), (0, 0, 0)) == pytest.approx((1, 2, 3))

    def test_90_around_z(self):
        result = _rotate_point(1, 0, 0, (0, 0, 0), (0, 0, 90))
        assert result == pytest.approx((0, 1, 0), abs=1e-10)

    def test_90_around_y(self):
        result = _rotate_point(1, 0, 0, (0, 0, 0), (0, 90, 0))
        assert result == pytest.approx((0, 0, -1), abs=1e-10)

    def test_90_around_x(self):
        result = _rotate_point(0, 1, 0, (0, 0, 0), (90, 0, 0))
        assert result == pytest.approx((0, 0, 1), abs=1e-10)

    def test_around_pivot(self):
        result = _rotate_point(2, 0, 0, (1, 0, 0), (0, 0, 90))
        assert result == pytest.approx((1, 1, 0), abs=1e-10)

    def test_360_returns_original(self):
        result = _rotate_point(3, 5, 7, (1, 2, 3), (360, 0, 0))
        assert result == pytest.approx((3, 5, 7), abs=1e-10)


# ---------------------------------------------------------------------------
# get_transformed_quads
# ---------------------------------------------------------------------------

class TestGetTransformedQuads:
    def test_no_rotation_unchanged(self):
        part = BoxPart("t", (0, 0, 0), (4, 4, 4), (0, 0))
        orig = part.get_face_quads()
        trans = get_transformed_quads(part)
        assert len(orig) == len(trans)
        for (n1, v1, u1), (n2, v2, u2) in zip(orig, trans):
            assert n1 == n2
            for a, b in zip(v1, v2):
                assert a == pytest.approx(b)

    def test_rotation_changes_vertices(self):
        part = BoxPart("t", (0, 0, 0), (4, 4, 4), (0, 0))
        part.rotation = (90, 0, 0)
        orig = part.get_face_quads()
        trans = get_transformed_quads(part)
        changed = False
        for (_, v1, _), (_, v2, _) in zip(orig, trans):
            for a, b in zip(v1, v2):
                if tuple(a) != pytest.approx(b, abs=0.01):
                    changed = True
        assert changed

    def test_uvs_preserved_after_rotation(self):
        part = BoxPart("t", (0, 0, 0), (4, 4, 4), (0, 0))
        part.rotation = (45, 30, 15)
        orig = part.get_face_quads()
        trans = get_transformed_quads(part)
        for (_, _, u1), (_, _, u2) in zip(orig, trans):
            for a, b in zip(u1, u2):
                assert a == pytest.approx(b)
