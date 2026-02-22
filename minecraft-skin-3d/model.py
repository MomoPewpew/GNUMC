"""
Minecraft player model geometry and UV mapping.

The skin texture is 64x64. Each body part is a rectangular box whose six faces
map to specific regions of the texture.  Minecraft uses a "box unwrap" layout:
for a box of size (W, H, D), the UV origin (u0, v0) anchors this pattern:

       D   W   D   W
    +----+----+----+----+       row 0: v0 .. v0+D  (top / bottom)
  D | top|    |bot |    |
    +----+----+----+----+       row 1: v0+D .. v0+D+H  (front/right/back/left)
  H |frt |rgt |bak |lft |
    +----+----+----+----+

Face order in the cross (left to right, top to bottom):
  Row 0:  col0 = top,  col1 = bottom  (Minecraft swaps depending on version)
  Row 1:  col0 = front, col1 = right, col2 = back, col3 = left

Actual Minecraft Java layout for a box at UV origin (u0, v0) with size (W, H, D):

  Top face:    u0+D,       v0,        W, D
  Bottom face: u0+D+W,     v0,        W, D
  Front face:  u0+D,       v0+D,      W, H
  Right face:  u0,         v0+D,      D, H
  Back face:   u0+D+W+D,   v0+D,      W, H
  Left face:   u0+D+W,     v0+D,      D, H
"""

import math


TEX_W = 64
TEX_H = 64


def _box_uvs(u0, v0, w, h, d, tex_w=TEX_W, tex_h=TEX_H):
    """
    Compute per-face UV rectangles for a Minecraft box unwrap.
    Returns dict mapping face name -> (u_min, v_min, u_max, v_max) in 0..1 range.

    Faces: 'front', 'back', 'left', 'right', 'top', 'bottom'
    """
    def norm(px_u, px_v, px_w, px_h):
        return (
            px_u / tex_w,
            px_v / tex_h,
            (px_u + px_w) / tex_w,
            (px_v + px_h) / tex_h,
        )

    return {
        "right":  norm(u0,             v0 + d,     d, h),
        "front":  norm(u0 + d,         v0 + d,     w, h),
        "left":   norm(u0 + d + w,     v0 + d,     d, h),
        "back":   norm(u0 + d + w + d, v0 + d,     w, h),
        "top":    norm(u0 + d,         v0,         w, d),
        "bottom": norm(u0 + d + w,     v0,         w, d),
    }


class BoxPart:
    """A single box in the player model."""

    __slots__ = ("name", "origin", "size", "uv_origin", "inflate", "uvs",
                 "pivot", "rotation")

    def __init__(self, name, origin, size, uv_origin, inflate=0.0,
                 pivot=None, rotation=None):
        self.name = name
        ox, oy, oz = origin
        w, h, d = size
        inf = inflate
        self.origin = (ox - inf, oy - inf, oz - inf)
        self.size = (w + 2 * inf, h + 2 * inf, d + 2 * inf)
        self.uv_origin = uv_origin
        self.inflate = inflate
        self.uvs = _box_uvs(uv_origin[0], uv_origin[1], w, h, d)
        self.pivot = pivot or (ox + w / 2, oy + h / 2, oz + d / 2)
        self.rotation = rotation or (0, 0, 0)

    def get_face_quads(self):
        """
        Return the 6 face quads as a list of (face_name, vertices, uvs).
        Each quad has 4 vertices (x,y,z) and 4 UV coords (u,v).
        Vertices are in world space (Y-up), faces wound counter-clockwise
        when viewed from outside.
        """
        x0, y0, z0 = self.origin
        w, h, d = self.size
        x1, y1, z1 = x0 + w, y0 + h, z0 + d

        quads = []

        # Front face (facing -Z direction, the face the player looks out of)
        face = "front"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)
        ]
        uvs = [
            (u1, v1), (u0, v1), (u0, v0), (u1, v0)
        ]
        quads.append((face, verts, uvs))

        # Back face (facing +Z)
        face = "back"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)
        ]
        uvs = [
            (u1, v1), (u0, v1), (u0, v0), (u1, v0)
        ]
        quads.append((face, verts, uvs))

        # Right face (facing -X)
        face = "right"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)
        ]
        uvs = [
            (u1, v1), (u0, v1), (u0, v0), (u1, v0)
        ]
        quads.append((face, verts, uvs))

        # Left face (facing +X)
        face = "left"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)
        ]
        uvs = [
            (u1, v1), (u0, v1), (u0, v0), (u1, v0)
        ]
        quads.append((face, verts, uvs))

        # Top face (facing +Y)
        face = "top"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)
        ]
        uvs = [
            (u0, v0), (u1, v0), (u1, v1), (u0, v1)
        ]
        quads.append((face, verts, uvs))

        # Bottom face (facing -Y)
        face = "bottom"
        uv = self.uvs[face]
        u0, v0, u1, v1 = uv
        verts = [
            (x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)
        ]
        uvs = [
            (u0, v0), (u1, v0), (u1, v1), (u0, v1)
        ]
        quads.append((face, verts, uvs))

        return quads


class PlayerModel:
    """Base class for a Minecraft player model."""

    def __init__(self):
        self.base_parts = []
        self.overlay_parts = []
        self._pose_rotations = {}

    def get_all_parts(self):
        return self.base_parts + self.overlay_parts

    def set_pose(self, pose_index):
        """
        0 = standing (default), 1 = walking, 2 = arms out (T-pose)
        """
        self._apply_pose(pose_index)

    def _apply_pose(self, pose_index):
        for part in self.get_all_parts():
            part.rotation = (0, 0, 0)

        if pose_index == 1:  # walking
            for part in self.get_all_parts():
                if "rightArm" in part.name or "rightSleeve" in part.name:
                    part.rotation = (30, 0, 0)
                elif "leftArm" in part.name or "leftSleeve" in part.name:
                    part.rotation = (-30, 0, 0)
                elif "rightLeg" in part.name or "rightPants" in part.name:
                    part.rotation = (-30, 0, 0)
                elif "leftLeg" in part.name or "leftPants" in part.name:
                    part.rotation = (30, 0, 0)

        elif pose_index == 2:  # T-pose / arms out
            for part in self.get_all_parts():
                if "rightArm" in part.name or "rightSleeve" in part.name:
                    part.rotation = (0, 0, 90)
                elif "leftArm" in part.name or "leftSleeve" in part.name:
                    part.rotation = (0, 0, -90)


def _rotate_point(px, py, pz, pivot, rotation_deg):
    """Rotate point around pivot by (rx, ry, rz) degrees (Euler XYZ)."""
    cx, cy, cz = pivot
    rx, ry, rz = [math.radians(a) for a in rotation_deg]

    x, y, z = px - cx, py - cy, pz - cz

    # Rotate around X
    cos_a, sin_a = math.cos(rx), math.sin(rx)
    y, z = cos_a * y - sin_a * z, sin_a * y + cos_a * z

    # Rotate around Y
    cos_a, sin_a = math.cos(ry), math.sin(ry)
    x, z = cos_a * x + sin_a * z, -sin_a * x + cos_a * z

    # Rotate around Z
    cos_a, sin_a = math.cos(rz), math.sin(rz)
    x, y = cos_a * x - sin_a * y, sin_a * x + cos_a * y

    return (x + cx, y + cy, z + cz)


def get_transformed_quads(part):
    """Get face quads with pose rotation applied."""
    quads = part.get_face_quads()
    rx, ry, rz = part.rotation
    if rx == 0 and ry == 0 and rz == 0:
        return quads

    transformed = []
    for face_name, verts, uvs in quads:
        new_verts = [
            _rotate_point(v[0], v[1], v[2], part.pivot, part.rotation)
            for v in verts
        ]
        transformed.append((face_name, new_verts, uvs))
    return transformed


class SteveModel(PlayerModel):
    """Classic Steve model with 4-pixel-wide arms."""

    def __init__(self):
        super().__init__()

        self.base_parts = [
            BoxPart("head",     (-4, 24, -4), (8, 8, 8),   (0, 0),
                    pivot=(0, 24, 0)),
            BoxPart("body",     (-4, 12, -2), (8, 12, 4),  (16, 16),
                    pivot=(0, 24, 0)),
            BoxPart("rightArm", (-8, 12, -2), (4, 12, 4),  (40, 16),
                    pivot=(-5, 22, 0)),
            BoxPart("leftArm",  (4, 12, -2),  (4, 12, 4),  (32, 48),
                    pivot=(5, 22, 0)),
            BoxPart("rightLeg", (-3.9, 0, -2),(4, 12, 4),  (0, 16),
                    pivot=(-1.9, 12, 0)),
            BoxPart("leftLeg",  (-0.1, 0, -2),(4, 12, 4),  (16, 48),
                    pivot=(1.9, 12, 0)),
        ]

        self.overlay_parts = [
            BoxPart("hat",          (-4, 24, -4), (8, 8, 8),  (32, 0),
                    inflate=0.5, pivot=(0, 24, 0)),
            BoxPart("jacket",       (-4, 12, -2), (8, 12, 4), (16, 32),
                    inflate=0.5, pivot=(0, 24, 0)),
            BoxPart("rightSleeve",  (-8, 12, -2), (4, 12, 4), (40, 32),
                    inflate=0.5, pivot=(-5, 22, 0)),
            BoxPart("leftSleeve",   (4, 12, -2),  (4, 12, 4), (48, 48),
                    inflate=0.5, pivot=(5, 22, 0)),
            BoxPart("rightPants",   (-3.9, 0, -2),(4, 12, 4), (0, 32),
                    inflate=0.5, pivot=(-1.9, 12, 0)),
            BoxPart("leftPants",    (-0.1, 0, -2),(4, 12, 4), (0, 48),
                    inflate=0.5, pivot=(1.9, 12, 0)),
        ]


class AlexModel(PlayerModel):
    """Slim Alex model with 3-pixel-wide arms."""

    def __init__(self):
        super().__init__()

        self.base_parts = [
            BoxPart("head",     (-4, 24, -4), (8, 8, 8),   (0, 0),
                    pivot=(0, 24, 0)),
            BoxPart("body",     (-4, 12, -2), (8, 12, 4),  (16, 16),
                    pivot=(0, 24, 0)),
            BoxPart("rightArm", (-7, 12, -2), (3, 12, 4),  (40, 16),
                    pivot=(-5, 21.5, 0)),
            BoxPart("leftArm",  (4, 12, -2),  (3, 12, 4),  (32, 48),
                    pivot=(5, 21.5, 0)),
            BoxPart("rightLeg", (-3.9, 0, -2),(4, 12, 4),  (0, 16),
                    pivot=(-1.9, 12, 0)),
            BoxPart("leftLeg",  (-0.1, 0, -2),(4, 12, 4),  (16, 48),
                    pivot=(1.9, 12, 0)),
        ]

        self.overlay_parts = [
            BoxPart("hat",          (-4, 24, -4), (8, 8, 8),  (32, 0),
                    inflate=0.5, pivot=(0, 24, 0)),
            BoxPart("jacket",       (-4, 12, -2), (8, 12, 4), (16, 32),
                    inflate=0.5, pivot=(0, 24, 0)),
            BoxPart("rightSleeve",  (-7, 12, -2), (3, 12, 4), (40, 32),
                    inflate=0.5, pivot=(-5, 21.5, 0)),
            BoxPart("leftSleeve",   (4, 12, -2),  (3, 12, 4), (48, 48),
                    inflate=0.5, pivot=(5, 21.5, 0)),
            BoxPart("rightPants",   (-3.9, 0, -2),(4, 12, 4), (0, 32),
                    inflate=0.5, pivot=(-1.9, 12, 0)),
            BoxPart("leftPants",    (-0.1, 0, -2),(4, 12, 4), (0, 48),
                    inflate=0.5, pivot=(1.9, 12, 0)),
        ]
