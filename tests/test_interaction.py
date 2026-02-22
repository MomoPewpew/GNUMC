"""Tests for interaction.py — ray casting and picking."""

import math
import pytest

from interaction import (
    _ray_triangle_intersect,
    _ray_quad_intersect,
    _unproject,
    RayCaster,
)
from model import SteveModel, AlexModel
from mathutil import perspective, look_at


# ---------------------------------------------------------------------------
# _ray_triangle_intersect
# ---------------------------------------------------------------------------

class TestRayTriangleIntersect:
    def test_hit_centered_triangle(self):
        v0 = (-1, -1, 0)
        v1 = (1, -1, 0)
        v2 = (0, 1, 0)
        uv0, uv1, uv2 = (0, 0), (1, 0), (0.5, 1)

        origin = (0, 0, 5)
        direction = (0, 0, -1)

        result = _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2)
        assert result is not None
        t, u, v = result
        assert t == pytest.approx(5.0)
        assert 0 <= u <= 1
        assert 0 <= v <= 1

    def test_miss_parallel_ray(self):
        v0 = (-1, -1, 0)
        v1 = (1, -1, 0)
        v2 = (0, 1, 0)
        uv0, uv1, uv2 = (0, 0), (1, 0), (0.5, 1)

        origin = (0, 0, 5)
        direction = (1, 0, 0)
        result = _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2)
        assert result is None

    def test_miss_behind_origin(self):
        v0 = (-1, -1, 0)
        v1 = (1, -1, 0)
        v2 = (0, 1, 0)
        uv0, uv1, uv2 = (0, 0), (1, 0), (0.5, 1)

        origin = (0, 0, -5)
        direction = (0, 0, -1)
        result = _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2)
        assert result is None

    def test_miss_outside_triangle(self):
        v0 = (-1, -1, 0)
        v1 = (1, -1, 0)
        v2 = (0, 1, 0)
        uv0, uv1, uv2 = (0, 0), (1, 0), (0.5, 1)

        origin = (10, 10, 5)
        direction = (0, 0, -1)
        result = _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2)
        assert result is None

    def test_uv_interpolation_at_vertex(self):
        """Ray hitting exactly v0 should return uv0."""
        v0 = (0, 0, 0)
        v1 = (2, 0, 0)
        v2 = (0, 2, 0)
        uv0, uv1, uv2 = (0, 0), (1, 0), (0, 1)

        origin = (0.001, 0.001, 5)
        direction = (0, 0, -1)
        result = _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2)
        assert result is not None
        _, u, v = result
        assert u == pytest.approx(0.0, abs=0.01)
        assert v == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# _ray_quad_intersect
# ---------------------------------------------------------------------------

class TestRayQuadIntersect:
    def test_hit_unit_quad(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        origin = (0.5, 0.5, 3)
        direction = (0, 0, -1)
        result = _ray_quad_intersect(origin, direction, verts, uvs)
        assert result is not None
        t, u, v = result
        assert t == pytest.approx(3.0)
        assert u == pytest.approx(0.5, abs=0.05)
        assert v == pytest.approx(0.5, abs=0.05)

    def test_miss_outside_quad(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        origin = (5, 5, 3)
        direction = (0, 0, -1)
        result = _ray_quad_intersect(origin, direction, verts, uvs)
        assert result is None

    def test_hit_second_triangle(self):
        """Ensure the second triangle (0,2,3) of the quad is also tested."""
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        origin = (0.1, 0.9, 2)
        direction = (0, 0, -1)
        result = _ray_quad_intersect(origin, direction, verts, uvs)
        assert result is not None


# ---------------------------------------------------------------------------
# _unproject
# ---------------------------------------------------------------------------

class TestUnproject:
    def test_center_of_screen(self):
        proj = perspective(45, 1.0, 0.1, 100)
        view = look_at((0, 0, 30), (0, 0, 0), (0, 1, 0))

        origin, direction = _unproject(300, 350, 600, 700, proj, view)
        assert origin is not None
        assert direction is not None
        assert direction[2] < 0, "should point roughly towards -Z"

    def test_returns_none_for_degenerate_matrices(self):
        proj = [0] * 16
        view = [0] * 16
        origin, direction = _unproject(100, 100, 600, 700, proj, view)
        assert origin is None
        assert direction is None


# ---------------------------------------------------------------------------
# RayCaster.pick — integration test
# ---------------------------------------------------------------------------

class TestRayCasterPick:
    def _setup_camera(self):
        proj = perspective(45, 600.0 / 700.0, 0.1, 500)
        view = look_at(
            (0, 14, 45),
            (0, 14, 0),
            (0, 1, 0),
        )
        return proj, view

    def test_pick_hits_model_center(self):
        """A ray aimed at the center of the viewport (body area) should hit."""
        proj, view = self._setup_camera()
        caster = RayCaster()
        model = SteveModel()
        result = caster.pick(300, 350, 600, 700, proj, view, model)
        assert result is not None
        px, py = result
        assert 0 <= px < 64
        assert 0 <= py < 64

    def test_pick_misses_empty_space(self):
        """A ray aimed far off to the side should miss."""
        proj, view = self._setup_camera()
        caster = RayCaster()
        model = SteveModel()
        result = caster.pick(0, 0, 600, 700, proj, view, model)
        assert result is None

    def test_pick_works_with_alex_model(self):
        proj, view = self._setup_camera()
        caster = RayCaster()
        model = AlexModel()
        result = caster.pick(300, 350, 600, 700, proj, view, model)
        assert result is not None

    def test_pick_works_with_posed_model(self):
        proj, view = self._setup_camera()
        caster = RayCaster()
        model = SteveModel()
        model.set_pose(1)
        result = caster.pick(300, 350, 600, 700, proj, view, model)
        assert result is not None
