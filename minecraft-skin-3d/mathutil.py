"""
Shared linear algebra utilities for the Minecraft skin 3D plugin.

All matrices are 4x4, stored as column-major flat lists of 16 floats
(OpenGL convention).  No external dependencies beyond the stdlib.
"""

import math


def identity():
    """Return the 4x4 identity matrix."""
    return [
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
    ]


def perspective(fov_deg, aspect, near, far):
    """Build a 4x4 perspective projection matrix (column-major flat list)."""
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    nf = near - far
    return [
        f / aspect, 0,  0,                         0,
        0,          f,  0,                         0,
        0,          0,  (far + near) / nf,        -1,
        0,          0,  (2 * far * near) / nf,     0,
    ]


def look_at(eye, center, up):
    """Build a 4x4 look-at view matrix (column-major flat list)."""
    fx = center[0] - eye[0]
    fy = center[1] - eye[1]
    fz = center[2] - eye[2]
    fl = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx /= fl; fy /= fl; fz /= fl

    sx = fy * up[2] - fz * up[1]
    sy = fz * up[0] - fx * up[2]
    sz = fx * up[1] - fy * up[0]
    sl = math.sqrt(sx * sx + sy * sy + sz * sz)
    sx /= sl; sy /= sl; sz /= sl

    ux = sy * fz - sz * fy
    uy = sz * fx - sx * fz
    uz = sx * fy - sy * fx

    return [
        sx,  ux, -fx, 0,
        sy,  uy, -fy, 0,
        sz,  uz, -fz, 0,
        -(sx * eye[0] + sy * eye[1] + sz * eye[2]),
        -(ux * eye[0] + uy * eye[1] + uz * eye[2]),
        (fx * eye[0] + fy * eye[1] + fz * eye[2]),
        1,
    ]


def mat4_multiply(a, b):
    """Multiply two column-major 4x4 matrices."""
    result = [0.0] * 16
    for row in range(4):
        for col in range(4):
            s = 0.0
            for k in range(4):
                s += a[k * 4 + row] * b[col * 4 + k]
            result[col * 4 + row] = s
    return result


def mat4_inverse(m):
    """Invert a 4x4 column-major matrix.  Returns None if singular."""
    inv = [0.0] * 16

    inv[0] = (m[5]*m[10]*m[15] - m[5]*m[11]*m[14] - m[9]*m[6]*m[15]
              + m[9]*m[7]*m[14] + m[13]*m[6]*m[11] - m[13]*m[7]*m[10])
    inv[4] = (-m[4]*m[10]*m[15] + m[4]*m[11]*m[14] + m[8]*m[6]*m[15]
              - m[8]*m[7]*m[14] - m[12]*m[6]*m[11] + m[12]*m[7]*m[10])
    inv[8] = (m[4]*m[9]*m[15] - m[4]*m[11]*m[13] - m[8]*m[5]*m[15]
              + m[8]*m[7]*m[13] + m[12]*m[5]*m[11] - m[12]*m[7]*m[9])
    inv[12] = (-m[4]*m[9]*m[14] + m[4]*m[10]*m[13] + m[8]*m[5]*m[14]
               - m[8]*m[6]*m[13] - m[12]*m[5]*m[10] + m[12]*m[6]*m[9])

    inv[1] = (-m[1]*m[10]*m[15] + m[1]*m[11]*m[14] + m[9]*m[2]*m[15]
              - m[9]*m[3]*m[14] - m[13]*m[2]*m[11] + m[13]*m[3]*m[10])
    inv[5] = (m[0]*m[10]*m[15] - m[0]*m[11]*m[14] - m[8]*m[2]*m[15]
              + m[8]*m[3]*m[14] + m[12]*m[2]*m[11] - m[12]*m[3]*m[10])
    inv[9] = (-m[0]*m[9]*m[15] + m[0]*m[11]*m[13] + m[8]*m[1]*m[15]
              - m[8]*m[3]*m[13] - m[12]*m[1]*m[11] + m[12]*m[3]*m[9])
    inv[13] = (m[0]*m[9]*m[14] - m[0]*m[10]*m[13] - m[8]*m[1]*m[14]
               + m[8]*m[2]*m[13] + m[12]*m[1]*m[10] - m[12]*m[2]*m[9])

    inv[2] = (m[1]*m[6]*m[15] - m[1]*m[7]*m[14] - m[5]*m[2]*m[15]
              + m[5]*m[3]*m[14] + m[13]*m[2]*m[7] - m[13]*m[3]*m[6])
    inv[6] = (-m[0]*m[6]*m[15] + m[0]*m[7]*m[14] + m[4]*m[2]*m[15]
              - m[4]*m[3]*m[14] - m[12]*m[2]*m[7] + m[12]*m[3]*m[6])
    inv[10] = (m[0]*m[5]*m[15] - m[0]*m[7]*m[13] - m[4]*m[1]*m[15]
               + m[4]*m[3]*m[13] + m[12]*m[1]*m[7] - m[12]*m[3]*m[5])
    inv[14] = (-m[0]*m[5]*m[14] + m[0]*m[6]*m[13] + m[4]*m[1]*m[14]
               - m[4]*m[2]*m[13] - m[12]*m[1]*m[6] + m[12]*m[2]*m[5])

    inv[3] = (-m[1]*m[6]*m[11] + m[1]*m[7]*m[10] + m[5]*m[2]*m[11]
              - m[5]*m[3]*m[10] - m[9]*m[2]*m[7] + m[9]*m[3]*m[6])
    inv[7] = (m[0]*m[6]*m[11] - m[0]*m[7]*m[10] - m[4]*m[2]*m[11]
              + m[4]*m[3]*m[10] + m[8]*m[2]*m[7] - m[8]*m[3]*m[6])
    inv[11] = (-m[0]*m[5]*m[11] + m[0]*m[7]*m[9] + m[4]*m[1]*m[11]
               - m[4]*m[3]*m[9] - m[8]*m[1]*m[7] + m[8]*m[3]*m[5])
    inv[15] = (m[0]*m[5]*m[10] - m[0]*m[6]*m[9] - m[4]*m[1]*m[10]
               + m[4]*m[2]*m[9] + m[8]*m[1]*m[6] - m[8]*m[2]*m[5])

    det = m[0]*inv[0] + m[1]*inv[4] + m[2]*inv[8] + m[3]*inv[12]
    if abs(det) < 1e-12:
        return None

    det = 1.0 / det
    return [x * det for x in inv]


def mat4_mul_vec4(m, v):
    """Multiply column-major 4x4 matrix by a 4-vector."""
    x, y, z, w = v
    return (
        m[0]*x + m[4]*y + m[8]*z  + m[12]*w,
        m[1]*x + m[5]*y + m[9]*z  + m[13]*w,
        m[2]*x + m[6]*y + m[10]*z + m[14]*w,
        m[3]*x + m[7]*y + m[11]*z + m[15]*w,
    )
