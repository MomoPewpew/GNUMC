"""
OpenGL renderer for the Minecraft player model.
Uses modern OpenGL 3.3 core profile with GTK GLArea.
"""

import math
import ctypes
import os
import struct

from OpenGL.GL import *
from OpenGL.GL import shaders as gl_shaders

from model import get_transformed_quads
from mathutil import (
    identity as _identity,
    perspective as _perspective,
    look_at as _look_at,
    mat4_multiply as _mat4_multiply,
    mat4_inverse as _mat4_inverse,
)

SHADER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shaders")


def _load_shader_source(filename):
    path = os.path.join(SHADER_DIR, filename)
    with open(path, "r") as f:
        return f.read()


class Renderer:
    """OpenGL renderer for the Minecraft player model."""

    def __init__(self):
        self.shader = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.texture_id = None
        self.selection_texture_id = None
        self.has_selection = False
        self.tex_width = 64
        self.tex_height = 64

        self._width = 600
        self._height = 700

        self._cam_yaw = 205.0
        self._cam_pitch = 15.0
        self._cam_distance = 45.0
        self._cam_target = [0.0, 16.0, 0.0]

        self.show_overlay = True

        self.proj_matrix = _identity()
        self.view_matrix = _identity()

        self._vertex_count = 0
        self._index_count = 0
        self._base_index_count = 0
        self._overlay_index_offset = 0

        self._time = 0.0

    def init_gl(self):
        vert_src = _load_shader_source("vertex.glsl")
        frag_src = _load_shader_source("fragment.glsl")

        vert = gl_shaders.compileShader(vert_src, GL_VERTEX_SHADER)
        frag = gl_shaders.compileShader(frag_src, GL_FRAGMENT_SHADER)
        self.shader = gl_shaders.compileProgram(vert, frag)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        blank = bytes([128, 128, 128, 255]) * (64 * 64)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 64, 64, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, blank)

        self.selection_texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.selection_texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        blank_sel = bytes([255]) * (64 * 64)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, 64, 64, 0,
                     GL_RED, GL_UNSIGNED_BYTE, blank_sel)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._update_matrices()

    def build_model_buffers(self, model):
        """Build VAO/VBO/EBO from the player model's box parts."""
        vertices = []
        indices = []
        vertex_offset = 0

        def _add_parts(parts):
            nonlocal vertex_offset
            for part in parts:
                quads = get_transformed_quads(part)
                for face_name, verts, uvs in quads:
                    # Compute face normal from first triangle
                    v0, v1, v2 = verts[0], verts[1], verts[2]
                    e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
                    e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
                    nx = e1[1]*e2[2] - e1[2]*e2[1]
                    ny = e1[2]*e2[0] - e1[0]*e2[2]
                    nz = e1[0]*e2[1] - e1[1]*e2[0]
                    nl = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if nl > 0:
                        nx /= nl; ny /= nl; nz /= nl

                    for i in range(4):
                        vertices.extend(verts[i])
                        vertices.extend(uvs[i])
                        vertices.extend((nx, ny, nz))

                    # Two triangles per quad
                    indices.extend([
                        vertex_offset, vertex_offset + 1, vertex_offset + 2,
                        vertex_offset, vertex_offset + 2, vertex_offset + 3,
                    ])
                    vertex_offset += 4

        _add_parts(model.base_parts)
        self._base_index_count = len(indices)
        self._overlay_index_offset = len(indices)

        _add_parts(model.overlay_parts)

        self._index_count = len(indices)
        self._vertex_count = vertex_offset

        vdata = struct.pack(f"{len(vertices)}f", *vertices)
        idata = struct.pack(f"{len(indices)}I", *indices)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, len(vdata), vdata, GL_DYNAMIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, len(idata), idata, GL_DYNAMIC_DRAW)

        stride = (3 + 2 + 3) * 4  # 8 floats * 4 bytes
        # position
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # UV
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        # normal
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(20))
        glEnableVertexAttribArray(2)

        glBindVertexArray(0)

    def update_texture(self, pixel_data, width, height):
        """Upload new skin texture data to the GL texture."""
        self.tex_width = width
        self.tex_height = height
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, pixel_data)

    def update_selection_texture(self, mask_data, width, height):
        """Upload selection mask (single channel) to the selection texture."""
        if mask_data is None:
            self.has_selection = False
            return
        self.has_selection = True
        glBindTexture(GL_TEXTURE_2D, self.selection_texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RED, width, height, 0,
                     GL_RED, GL_UNSIGNED_BYTE, mask_data)

    def resize(self, width, height):
        self._width = max(width, 1)
        self._height = max(height, 1)
        self._update_matrices()

    def render(self, model, show_grid=False, hover_pixel=None):
        """Render the full model."""
        self._time += 0.016

        glViewport(0, 0, self._width, self._height)
        glClearColor(0.58, 0.60, 0.64, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self._update_matrices()

        glUseProgram(self.shader)

        proj_loc = glGetUniformLocation(self.shader, "uProjection")
        view_loc = glGetUniformLocation(self.shader, "uView")
        model_loc = glGetUniformLocation(self.shader, "uModel")
        tex_loc = glGetUniformLocation(self.shader, "uTexture")
        sel_loc = glGetUniformLocation(self.shader, "uSelectionMask")
        has_sel_loc = glGetUniformLocation(self.shader, "uHasSelection")
        time_loc = glGetUniformLocation(self.shader, "uTime")
        grid_loc = glGetUniformLocation(self.shader, "uShowGrid")
        hover_loc = glGetUniformLocation(self.shader, "uHoverPixel")
        texsize_loc = glGetUniformLocation(self.shader, "uTexSize")

        glUniformMatrix4fv(proj_loc, 1, GL_FALSE,
                          (ctypes.c_float * 16)(*self.proj_matrix))
        glUniformMatrix4fv(view_loc, 1, GL_FALSE,
                          (ctypes.c_float * 16)(*self.view_matrix))

        identity = _identity()
        glUniformMatrix4fv(model_loc, 1, GL_FALSE,
                          (ctypes.c_float * 16)(*identity))

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glUniform1i(tex_loc, 0)

        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.selection_texture_id)
        glUniform1i(sel_loc, 1)

        glUniform1i(has_sel_loc, 1 if self.has_selection else 0)
        glUniform1f(time_loc, self._time)
        glUniform1i(grid_loc, 1 if show_grid else 0)
        glUniform2f(texsize_loc, float(self.tex_width), float(self.tex_height))

        if hover_pixel:
            glUniform2f(hover_loc, float(hover_pixel[0]), float(hover_pixel[1]))
        else:
            glUniform2f(hover_loc, -1.0, -1.0)

        glBindVertexArray(self.vao)

        # Draw base parts (opaque)
        glDepthMask(GL_TRUE)
        glDrawElements(GL_TRIANGLES, self._base_index_count,
                      GL_UNSIGNED_INT, ctypes.c_void_p(0))

        # Draw overlay parts (potentially transparent)
        glDepthMask(GL_FALSE)
        overlay_count = self._index_count - self._base_index_count
        if overlay_count > 0 and self.show_overlay:
            offset_bytes = self._base_index_count * 4
            glDrawElements(GL_TRIANGLES, overlay_count,
                          GL_UNSIGNED_INT, ctypes.c_void_p(offset_bytes))

        glDepthMask(GL_TRUE)
        glBindVertexArray(0)
        glUseProgram(0)

    def camera_rotate(self, dx, dy):
        self._cam_yaw += dx * 0.5
        self._cam_pitch += dy * 0.5
        self._cam_pitch = max(-89.0, min(89.0, self._cam_pitch))

    def camera_zoom(self, delta):
        self._cam_distance += delta * 2.0
        self._cam_distance = max(10.0, min(120.0, self._cam_distance))

    def reset_camera(self):
        self._cam_yaw = 205.0
        self._cam_pitch = 15.0
        self._cam_distance = 45.0
        self._cam_target = [0.0, 16.0, 0.0]

    def set_pose(self, pose_index):
        pass  # Pose is applied in the model; renderer just rebuilds buffers.

    def _update_matrices(self):
        aspect = self._width / max(self._height, 1)
        self.proj_matrix = _perspective(45.0, aspect, 0.1, 500.0)

        yaw_rad = math.radians(self._cam_yaw)
        pitch_rad = math.radians(self._cam_pitch)

        eye_x = self._cam_target[0] + self._cam_distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        eye_y = self._cam_target[1] + self._cam_distance * math.sin(pitch_rad)
        eye_z = self._cam_target[2] + self._cam_distance * math.cos(pitch_rad) * math.cos(yaw_rad)

        self.view_matrix = _look_at(
            (eye_x, eye_y, eye_z),
            tuple(self._cam_target),
            (0.0, 1.0, 0.0),
        )
