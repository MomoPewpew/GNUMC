"""
Ray casting and interaction: maps mouse clicks on the 3D view back to
pixel coordinates in the 64x64 skin texture.

Pipeline:
  1. Unproject screen coords to a ray in world space
  2. Intersect ray with each face quad of the model
  3. Compute UV at the hit point
  4. Convert UV to pixel coordinates
"""

import math
from model import get_transformed_quads, TEX_W, TEX_H
from mathutil import mat4_mul_vec4 as _mat4_mul_vec4, mat4_inverse as _mat4_inverse


def _unproject(mx, my, viewport_w, viewport_h, proj, view):
    """
    Convert screen coords (mx, my) to a ray (origin, direction) in world space.
    mx, my are in GTK widget coordinates (origin top-left).
    """
    ndc_x = (2.0 * mx / viewport_w) - 1.0
    ndc_y = 1.0 - (2.0 * my / viewport_h)

    inv_proj = _mat4_inverse(proj)
    inv_view = _mat4_inverse(view)
    if inv_proj is None or inv_view is None:
        return None, None

    near_clip = (ndc_x, ndc_y, -1.0, 1.0)
    far_clip = (ndc_x, ndc_y, 1.0, 1.0)

    near_eye = _mat4_mul_vec4(inv_proj, near_clip)
    far_eye = _mat4_mul_vec4(inv_proj, far_clip)

    if abs(near_eye[3]) < 1e-12 or abs(far_eye[3]) < 1e-12:
        return None, None
    near_eye = tuple(c / near_eye[3] for c in near_eye)
    far_eye = tuple(c / far_eye[3] for c in far_eye)

    near_world = _mat4_mul_vec4(inv_view, near_eye)
    far_world = _mat4_mul_vec4(inv_view, far_eye)

    origin = (near_world[0], near_world[1], near_world[2])
    direction = (
        far_world[0] - near_world[0],
        far_world[1] - near_world[1],
        far_world[2] - near_world[2],
    )
    dl = math.sqrt(direction[0]**2 + direction[1]**2 + direction[2]**2)
    if dl < 1e-12:
        return None, None
    direction = (direction[0]/dl, direction[1]/dl, direction[2]/dl)

    return origin, direction


def _ray_quad_intersect(origin, direction, verts, uvs):
    """
    Intersect a ray with a quad (4 vertices, 4 UVs).
    Returns (t, u_tex, v_tex) or None.
    Uses two-triangle decomposition: (0,1,2) and (0,2,3).
    """
    result = _ray_triangle_intersect(
        origin, direction,
        verts[0], verts[1], verts[2],
        uvs[0], uvs[1], uvs[2],
    )
    if result is not None:
        return result

    return _ray_triangle_intersect(
        origin, direction,
        verts[0], verts[2], verts[3],
        uvs[0], uvs[2], uvs[3],
    )


def _ray_triangle_intersect(origin, direction, v0, v1, v2, uv0, uv1, uv2):
    """
    Moller-Trumbore ray-triangle intersection.
    Returns (t, u_tex, v_tex) where u_tex/v_tex are interpolated texture coords,
    or None if no hit.
    """
    EPSILON = 1e-7
    e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
    e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])

    h = (
        direction[1]*e2[2] - direction[2]*e2[1],
        direction[2]*e2[0] - direction[0]*e2[2],
        direction[0]*e2[1] - direction[1]*e2[0],
    )
    a = e1[0]*h[0] + e1[1]*h[1] + e1[2]*h[2]
    if abs(a) < EPSILON:
        return None

    f = 1.0 / a
    s = (origin[0]-v0[0], origin[1]-v0[1], origin[2]-v0[2])
    u = f * (s[0]*h[0] + s[1]*h[1] + s[2]*h[2])
    if u < 0.0 or u > 1.0:
        return None

    q = (
        s[1]*e1[2] - s[2]*e1[1],
        s[2]*e1[0] - s[0]*e1[2],
        s[0]*e1[1] - s[1]*e1[0],
    )
    v = f * (direction[0]*q[0] + direction[1]*q[1] + direction[2]*q[2])
    if v < 0.0 or u + v > 1.0:
        return None

    t = f * (e2[0]*q[0] + e2[1]*q[1] + e2[2]*q[2])
    if t < EPSILON:
        return None

    w0 = 1.0 - u - v
    tex_u = w0 * uv0[0] + u * uv1[0] + v * uv2[0]
    tex_v = w0 * uv0[1] + u * uv1[1] + v * uv2[1]

    return (t, tex_u, tex_v)


class RayCaster:
    """Handles picking: screen coords -> pixel coords in the skin texture."""

    def pick(self, mx, my, viewport_w, viewport_h, proj, view, model,
             overlay_visible=True):
        """
        Given mouse position (mx, my) in widget coords, return the (px, py)
        pixel coordinate in the skin texture, or None if no hit.

        When *overlay_visible* is False, only base parts are tested.
        """
        origin, direction = _unproject(mx, my, viewport_w, viewport_h, proj, view)
        if origin is None:
            return None

        best_t = float('inf')
        best_uv = None

        parts = model.get_all_parts() if overlay_visible else model.base_parts
        for part in parts:
            quads = get_transformed_quads(part)
            for face_name, verts, uvs in quads:
                hit = _ray_quad_intersect(origin, direction, verts, uvs)
                if hit is not None:
                    t, tex_u, tex_v = hit
                    if t < best_t:
                        best_t = t
                        best_uv = (tex_u, tex_v)

        if best_uv is None:
            return None

        tex_u, tex_v = best_uv
        px = int(tex_u * TEX_W)
        py = int(tex_v * TEX_H)

        px = max(0, min(TEX_W - 1, px))
        py = max(0, min(TEX_H - 1, py))

        return (px, py)
