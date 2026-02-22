#!/usr/bin/env python3
"""
Standalone 3D Minecraft skin preview — no GIMP required.

Usage:
    python standalone_preview.py [skin.png]
    python standalone_preview.py --watch skin.png   # auto-reload on change

If no skin file is provided, a colorful test texture is generated so the
preview works out of the box.
"""

import sys
import os
import argparse

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft-skin-3d")
sys.path.insert(0, os.path.join(PLUGIN_DIR, "vendor"))
sys.path.insert(0, PLUGIN_DIR)

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from model import SteveModel, AlexModel
from renderer import Renderer
from interaction import RayCaster


# ---------------------------------------------------------------------------
# Texture loading helpers
# ---------------------------------------------------------------------------

def load_skin_texture(path):
    """Load a PNG skin file via GdkPixbuf and return (RGBA bytes, w, h)."""
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    width = pixbuf.get_width()
    height = pixbuf.get_height()
    has_alpha = pixbuf.get_has_alpha()
    rowstride = pixbuf.get_rowstride()
    raw = pixbuf.get_pixels()
    n_channels = pixbuf.get_n_channels()

    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            src = y * rowstride + x * n_channels
            dst = (y * width + x) * 4
            pixels[dst] = raw[src]
            pixels[dst + 1] = raw[src + 1]
            pixels[dst + 2] = raw[src + 2]
            pixels[dst + 3] = raw[src + 3] if has_alpha else 255

    return bytes(pixels), width, height


def generate_test_texture(width=64, height=64):
    """Produce a colorful test texture matching the Minecraft UV layout."""
    pixels = bytearray(width * height * 4)

    regions = [
        # (x0, y0, x1, y1), (r, g, b), alpha
        ((8, 0, 24, 8), (200, 50, 50), 255),       # head top/bottom
        ((0, 8, 32, 16), (180, 40, 40), 255),       # head sides
        ((20, 16, 36, 20), (50, 50, 200), 255),     # body top/bottom
        ((16, 20, 40, 32), (40, 40, 180), 255),     # body sides
        ((40, 16, 56, 32), (50, 180, 50), 255),     # right arm
        ((0, 16, 16, 32), (150, 50, 150), 255),     # right leg
        ((32, 48, 64, 64), (50, 150, 50), 255),     # left arm
        ((16, 48, 32, 64), (120, 50, 120), 255),    # left leg
        ((32, 0, 64, 16), (255, 255, 100), 128),    # hat overlay
        ((16, 32, 40, 48), (100, 100, 255), 128),   # body overlay
        ((40, 32, 56, 48), (100, 200, 100), 128),   # right sleeve overlay
        ((0, 32, 16, 48), (180, 100, 180), 128),    # right pants overlay
        ((48, 48, 64, 64), (100, 200, 100), 128),   # left sleeve overlay
        ((0, 48, 16, 64), (180, 100, 180), 128),    # left pants overlay
    ]

    for (x0, y0, x1, y1), (r, g, b), a in regions:
        for y in range(y0, min(y1, height)):
            for x in range(x0, min(x1, width)):
                idx = (y * width + x) * 4
                bright = 1.0 if (x + y) % 2 == 0 else 0.85
                pixels[idx] = int(r * bright)
                pixels[idx + 1] = int(g * bright)
                pixels[idx + 2] = int(b * bright)
                pixels[idx + 3] = a

    return bytes(pixels), width, height


# ---------------------------------------------------------------------------
# Standalone preview window
# ---------------------------------------------------------------------------

class StandalonePreviewWindow(Gtk.Window):

    def __init__(self, texture_data, tex_width, tex_height):
        super().__init__(title="Minecraft Skin 3D Preview (Standalone)")
        self.set_default_size(600, 700)

        self._texture_data = texture_data
        self._tex_width = tex_width
        self._tex_height = tex_height

        self.renderer = None
        self.ray_caster = RayCaster()
        self.steve_model = SteveModel()
        self.alex_model = AlexModel()
        self.use_alex = False
        self._current_pose = 0

        self._rotate_active = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._hover_pixel = None
        self._show_grid = False
        self._show_overlay = True

        self._build_ui()
        self._connect_events()

    @property
    def active_model(self):
        return self.alex_model if self.use_alex else self.steve_model

    # -- UI setup -----------------------------------------------------------

    def _build_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(6)
        toolbar.set_margin_end(6)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        model_label = Gtk.Label(label="Model:")
        toolbar.pack_start(model_label, False, False, 0)

        self.model_combo = Gtk.ComboBoxText()
        self.model_combo.append_text("Steve (classic)")
        self.model_combo.append_text("Alex (slim)")
        self.model_combo.set_active(0)
        self.model_combo.connect("changed", self._on_model_changed)
        toolbar.pack_start(self.model_combo, False, False, 0)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.pack_start(sep1, False, False, 4)

        self.grid_toggle = Gtk.ToggleButton(label="Grid")
        self.grid_toggle.connect("toggled", self._on_grid_toggled)
        toolbar.pack_start(self.grid_toggle, False, False, 0)

        self.overlay_toggle = Gtk.ToggleButton(label="Outer Layer")
        self.overlay_toggle.set_active(True)
        self.overlay_toggle.connect("toggled", self._on_overlay_toggled)
        toolbar.pack_start(self.overlay_toggle, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.pack_start(sep2, False, False, 4)

        self.coord_label = Gtk.Label(label="Pixel: -")
        self.coord_label.set_xalign(0)
        toolbar.pack_start(self.coord_label, True, True, 0)

        reset_btn = Gtk.Button(label="Reset View")
        reset_btn.connect("clicked", self._on_reset_view)
        toolbar.pack_end(reset_btn, False, False, 0)

        pose_label = Gtk.Label(label="Pose:")
        toolbar.pack_end(pose_label, False, False, 0)

        self.pose_combo = Gtk.ComboBoxText()
        self.pose_combo.append_text("Standing")
        self.pose_combo.append_text("Walking")
        self.pose_combo.append_text("Arms Out")
        self.pose_combo.set_active(0)
        self.pose_combo.connect("changed", self._on_pose_changed)
        toolbar.pack_end(self.pose_combo, False, False, 0)

        vbox.pack_start(toolbar, False, False, 0)

        self.gl_area = Gtk.GLArea()
        self.gl_area.set_has_depth_buffer(True)
        self.gl_area.set_has_stencil_buffer(False)
        self.gl_area.set_required_version(3, 3)
        self.gl_area.set_can_focus(True)
        self.gl_area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
        )

        self.gl_area.connect("realize", self._on_realize)
        self.gl_area.connect("render", self._on_render)
        self.gl_area.connect("resize", self._on_resize)
        self.gl_area.connect("button-press-event", self._on_button_press)
        self.gl_area.connect("button-release-event", self._on_button_release)
        self.gl_area.connect("motion-notify-event", self._on_motion)
        self.gl_area.connect("scroll-event", self._on_scroll)

        vbox.pack_start(self.gl_area, True, True, 0)

        self.status_bar = Gtk.Label(
            label="Left/Middle-drag: rotate | Scroll: zoom | G: toggle grid"
        )
        self.status_bar.set_xalign(0)
        self.status_bar.set_margin_start(6)
        self.status_bar.set_margin_top(2)
        self.status_bar.set_margin_bottom(2)
        vbox.pack_start(self.status_bar, False, False, 0)

    def _connect_events(self):
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self._on_key_press)

    # -- GL events ----------------------------------------------------------

    def _on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            return
        self.renderer = Renderer()
        self.renderer.init_gl()
        self.renderer.build_model_buffers(self.active_model)
        self.renderer.update_texture(
            self._texture_data, self._tex_width, self._tex_height,
        )

    def _on_render(self, area, ctx):
        if self.renderer is None:
            return True
        self.renderer.render(
            self.active_model,
            show_grid=self._show_grid,
            hover_pixel=self._hover_pixel,
        )
        return True

    def _on_resize(self, area, width, height):
        if self.renderer:
            self.renderer.resize(width, height)

    # -- Mouse / keyboard ---------------------------------------------------

    def _on_button_press(self, widget, event):
        if event.button in (1, 2):
            self._rotate_active = True
            self._last_mouse_x = event.x
            self._last_mouse_y = event.y
            return True
        return False

    def _on_button_release(self, widget, event):
        if event.button in (1, 2):
            self._rotate_active = False
            return True
        return False

    def _on_motion(self, widget, event):
        if self._rotate_active:
            dx = event.x - self._last_mouse_x
            dy = event.y - self._last_mouse_y
            self._last_mouse_x = event.x
            self._last_mouse_y = event.y
            if self.renderer:
                self.renderer.camera_rotate(dx, dy)
                self.gl_area.queue_render()
            return True
        self._handle_hover(event.x, event.y)
        return True

    def _on_scroll(self, widget, event):
        if self.renderer is None:
            return False
        if event.direction == Gdk.ScrollDirection.UP:
            self.renderer.camera_zoom(-1)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.renderer.camera_zoom(1)
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = event.get_scroll_deltas()
            self.renderer.camera_zoom(dy)
        self.gl_area.queue_render()
        return True

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_g:
            self._show_grid = not self._show_grid
            self.grid_toggle.set_active(self._show_grid)
            self.gl_area.queue_render()
            return True
        return False

    # -- Toolbar handlers ---------------------------------------------------

    def _on_model_changed(self, combo):
        self.use_alex = combo.get_active() == 1
        self.active_model.set_pose(self._current_pose)
        if self.renderer:
            self.gl_area.make_current()
            self.renderer.build_model_buffers(self.active_model)
            self.gl_area.queue_render()

    def _on_grid_toggled(self, btn):
        self._show_grid = btn.get_active()
        self.gl_area.queue_render()

    def _on_overlay_toggled(self, btn):
        self._show_overlay = btn.get_active()
        if self.renderer:
            self.renderer.show_overlay = self._show_overlay
            self.gl_area.queue_render()

    def _on_pose_changed(self, combo):
        if self.renderer is None:
            return
        self._current_pose = combo.get_active()
        self.active_model.set_pose(self._current_pose)
        self.gl_area.make_current()
        self.renderer.build_model_buffers(self.active_model)
        self.gl_area.queue_render()

    def _on_reset_view(self, btn):
        if self.renderer:
            self.renderer.reset_camera()
            self.gl_area.queue_render()

    # -- Hover --------------------------------------------------------------

    def _handle_hover(self, mx, my):
        if self.renderer is None:
            return
        alloc = self.gl_area.get_allocation()
        hit = self.ray_caster.pick(
            mx, my, alloc.width, alloc.height,
            self.renderer.proj_matrix, self.renderer.view_matrix,
            self.active_model,
            overlay_visible=self._show_overlay,
        )
        if hit:
            px, py = hit
            self._hover_pixel = (px, py)
            self.coord_label.set_text(f"Pixel: ({px}, {py})")
        else:
            self._hover_pixel = None
            self.coord_label.set_text("Pixel: -")
        self.gl_area.queue_render()

    # -- Public API for live-reload -----------------------------------------

    def update_texture(self, texture_data, width, height):
        self._texture_data = texture_data
        self._tex_width = width
        self._tex_height = height
        if self.renderer:
            self.gl_area.make_current()
            self.renderer.update_texture(texture_data, width, height)
            self.gl_area.queue_render()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Standalone 3D Minecraft skin preview (no GIMP required)",
    )
    parser.add_argument(
        "skin", nargs="?", default=None,
        help="Path to a 64x64 PNG skin file. Omit for a generated test texture.",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Watch the skin file for changes and auto-reload.",
    )
    args = parser.parse_args()

    if args.skin:
        texture_data, tex_w, tex_h = load_skin_texture(args.skin)
        print(f"Loaded skin: {args.skin} ({tex_w}x{tex_h})")
    else:
        texture_data, tex_w, tex_h = generate_test_texture()
        print("Using generated test texture (64x64)")

    win = StandalonePreviewWindow(texture_data, tex_w, tex_h)
    win.show_all()

    if args.watch and args.skin:
        last_mtime = [os.path.getmtime(args.skin)]

        def _check_file():
            try:
                mtime = os.path.getmtime(args.skin)
                if mtime != last_mtime[0]:
                    last_mtime[0] = mtime
                    data, w, h = load_skin_texture(args.skin)
                    win.update_texture(data, w, h)
                    print(f"Reloaded: {args.skin}")
            except Exception as e:
                print(f"Watch error: {e}")
            return True

        GLib.timeout_add(500, _check_file)

    Gtk.main()


if __name__ == "__main__":
    main()
