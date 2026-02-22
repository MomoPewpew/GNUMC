"""Tests for mathutil.py — pure linear algebra, no OpenGL dependency."""

import math
import pytest

from mathutil import (
    identity, perspective, look_at,
    mat4_multiply, mat4_inverse, mat4_mul_vec4,
)


class TestIdentity:
    def test_diagonal_ones(self):
        m = identity()
        for i in range(4):
            assert m[i * 4 + i] == 1.0

    def test_off_diagonal_zeros(self):
        m = identity()
        for col in range(4):
            for row in range(4):
                if col != row:
                    assert m[col * 4 + row] == 0.0

    def test_length_16(self):
        assert len(identity()) == 16


class TestMat4MulVec4:
    def test_identity_preserves_vector(self):
        v = (3.0, 7.0, -2.0, 1.0)
        result = mat4_mul_vec4(identity(), v)
        assert result == pytest.approx(v)

    def test_translation_via_manual_matrix(self):
        m = identity()
        m[12], m[13], m[14] = 10.0, 20.0, 30.0  # column-major translation
        result = mat4_mul_vec4(m, (0, 0, 0, 1))
        assert result == pytest.approx((10, 20, 30, 1))

    def test_scale_via_manual_matrix(self):
        m = identity()
        m[0], m[5], m[10] = 2.0, 3.0, 4.0
        result = mat4_mul_vec4(m, (1, 1, 1, 1))
        assert result == pytest.approx((2, 3, 4, 1))


class TestMat4Inverse:
    def test_identity_inverse_is_identity(self):
        inv = mat4_inverse(identity())
        assert inv is not None
        assert inv == pytest.approx(identity())

    def test_a_times_a_inv_is_identity(self):
        m = identity()
        m[12], m[13], m[14] = 5.0, -3.0, 7.0
        m[0], m[5], m[10] = 2.0, 0.5, 3.0
        inv = mat4_inverse(m)
        assert inv is not None
        product = mat4_multiply(m, inv)
        assert product == pytest.approx(identity(), abs=1e-9)

    def test_singular_returns_none(self):
        m = [0.0] * 16
        assert mat4_inverse(m) is None

    def test_look_at_inverse_roundtrip(self):
        v = look_at((10, 5, 10), (0, 0, 0), (0, 1, 0))
        inv = mat4_inverse(v)
        assert inv is not None
        product = mat4_multiply(v, inv)
        assert product == pytest.approx(identity(), abs=1e-9)


class TestMat4Multiply:
    def test_identity_times_a_is_a(self):
        a = look_at((5, 5, 5), (0, 0, 0), (0, 1, 0))
        result = mat4_multiply(identity(), a)
        assert result == pytest.approx(a)

    def test_a_times_identity_is_a(self):
        a = perspective(45, 1.0, 0.1, 100)
        result = mat4_multiply(a, identity())
        assert result == pytest.approx(a)

    def test_not_commutative(self):
        a = perspective(45, 1.0, 0.1, 100)
        b = look_at((5, 5, 5), (0, 0, 0), (0, 1, 0))
        ab = mat4_multiply(a, b)
        ba = mat4_multiply(b, a)
        with pytest.raises(AssertionError):
            assert ab == pytest.approx(ba, abs=1e-6)


class TestPerspective:
    def test_returns_16_floats(self):
        assert len(perspective(45, 1.0, 0.1, 100)) == 16

    def test_fov_affects_diagonal(self):
        narrow = perspective(30, 1.0, 0.1, 100)
        wide = perspective(90, 1.0, 0.1, 100)
        assert narrow[0] > wide[0]
        assert narrow[5] > wide[5]

    def test_aspect_ratio(self):
        m = perspective(45, 2.0, 0.1, 100)
        assert m[0] == pytest.approx(m[5] / 2.0)


class TestLookAt:
    def test_returns_16_floats(self):
        assert len(look_at((0, 0, 5), (0, 0, 0), (0, 1, 0))) == 16

    def test_origin_at_target_direction(self):
        """Camera at (0,0,10) looking at origin: the view matrix should place
        the origin somewhere along the -Z axis in eye space."""
        v = look_at((0, 0, 10), (0, 0, 0), (0, 1, 0))
        origin_eye = mat4_mul_vec4(v, (0, 0, 0, 1))
        assert origin_eye[2] < 0, "origin should be in front of camera (negative Z)"

    def test_invertible(self):
        v = look_at((3, 4, 5), (0, 0, 0), (0, 1, 0))
        assert mat4_inverse(v) is not None
