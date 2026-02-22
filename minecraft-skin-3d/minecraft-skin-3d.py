#!/usr/bin/env python3
"""
GIMP 3 Plugin: Minecraft Skin 3D Editor
Opens a live 3D preview of a Minecraft skin wrapped around a player model.
Supports bidirectional interaction: paint/select on the 3D view or the 2D canvas.
"""

import sys
import gi

gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gimp, GimpUi, Gtk, Gdk, GLib
import hashlib
import os
import traceback

try:
    gi.require_version("Gegl", "0.4")
    from gi.repository import Gegl as _Gegl
except Exception:
    _Gegl = None

_LOG_PATH = os.path.join(os.path.expanduser("~"), ".config", "GIMP", "3.0",
                         "minecraft-skin-3d.log")


def _log(msg):
    try:
        with open(_LOG_PATH, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "vendor"))
sys.path.insert(0, PLUGIN_DIR)


def _lazy_import():
    """Import OpenGL-dependent modules only when the plugin is actually run,
    not during GIMP's registration query.  This avoids a hard crash when
    PyOpenGL is not yet installed."""
    global SteveModel, AlexModel, Renderer, RayCaster
    from model import SteveModel, AlexModel
    from renderer import Renderer
    from interaction import RayCaster


class MinecraftSkin3DWindow(Gtk.Window):
    """Main 3D preview window with GLArea and interaction handling.

    GIMP 3 plugins run as separate processes; true docking inside the GIMP
    canvas (like the Layers or Channels panel) requires GIMP's internal C API
    and is not available to plug-ins.  We use GimpUi.window_set_transient()
    so the preview stays on top of and grouped with the GIMP image window
    (e.g. in the taskbar and when Alt-Tabbing).
    """

    def __init__(self, image, drawable):
        super().__init__(title="Minecraft Skin 3D Preview")
        self.image = image
        self.drawable = drawable
        self.set_default_size(600, 700)

        try:
            GimpUi.window_set_transient(self)
        except Exception:
            pass

        self.renderer = None
        self.ray_caster = RayCaster()
        self.model = SteveModel()
        self.alex_model = AlexModel()
        self.use_alex = False

        self._last_texture_hash = None
        self._last_selection_hash = None
        self._drag_active = False
        self._drag_button = 0
        self._last_drag_pixel = None
        self._drag_modifiers = {}
        self._fuzzy_drag = None
        self._drag_start_mx = 0
        self._rotate_active = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._hover_pixel = None
        self._pdb_diagnosed = False
        self._show_grid = False
        self._show_overlay = True
        self._show_selection_overlay = True
        self.has_selection_cached = False

        self._build_ui()
        self._connect_events()

        try:
            self.image.undo_enable()
        except Exception:
            pass

        GLib.timeout_add(50, self._poll_texture)

    @property
    def active_model(self):
        return self.alex_model if self.use_alex else self.model

    def _get_drawable(self):
        """Return the active drawable, compatible with GIMP 3.0+."""
        drawables = self.image.get_selected_drawables()
        if drawables:
            return drawables[0]
        layers = self.image.get_layers()
        if layers:
            return layers[0]
        return None

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

        tool_label = Gtk.Label(label="Tool:")
        toolbar.pack_start(tool_label, False, False, 0)

        self.tool_combo = Gtk.ComboBoxText()
        self.tool_combo.append_text("Pencil")
        self.tool_combo.append_text("Paintbrush")
        self.tool_combo.append_text("Eraser")
        self.tool_combo.append_text("Airbrush")
        self.tool_combo.append_text("Bucket Fill")
        self.tool_combo.append_text("Color Picker")
        self.tool_combo.append_text("Fuzzy Select")
        self.tool_combo.set_active(0)
        self.tool_combo.set_tooltip_text(
            "Choose which GIMP tool to use when clicking on the 3D view")
        toolbar.pack_start(self.tool_combo, False, False, 0)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.pack_start(sep3, False, False, 4)

        undo_btn = Gtk.Button(label="Undo")
        undo_btn.set_tooltip_text("Undo last action in GIMP (Ctrl+Z)")
        undo_btn.connect("clicked", lambda _b: self._gimp_undo())
        toolbar.pack_start(undo_btn, False, False, 0)

        redo_btn = Gtk.Button(label="Redo")
        redo_btn.set_tooltip_text("Redo last undone action in GIMP (Ctrl+Y)")
        redo_btn.connect("clicked", lambda _b: self._gimp_redo())
        toolbar.pack_start(redo_btn, False, False, 0)

        sep4 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.pack_start(sep4, False, False, 4)

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
            | Gdk.EventMask.KEY_PRESS_MASK
        )

        self.gl_area.connect("realize", self._on_realize)
        self.gl_area.connect("render", self._on_render)
        self.gl_area.connect("resize", self._on_resize)
        self.gl_area.connect("button-press-event", self._on_button_press)
        self.gl_area.connect("button-release-event", self._on_button_release)
        self.gl_area.connect("motion-notify-event", self._on_motion)
        self.gl_area.connect("scroll-event", self._on_scroll)
        self.gl_area.connect("key-press-event", self._on_key_press)

        vbox.pack_start(self.gl_area, True, True, 0)

        self.status_bar = Gtk.Label(label="Left: tool | Middle/Right: rotate | Scroll: zoom | Shift/Ctrl: modify | Ctrl+Z/Y: undo/redo")
        self.status_bar.set_xalign(0)
        self.status_bar.set_margin_start(6)
        self.status_bar.set_margin_top(2)
        self.status_bar.set_margin_bottom(2)
        vbox.pack_start(self.status_bar, False, False, 0)

    def _connect_events(self):
        self.connect("destroy", self._on_destroy)
        self.connect("key-press-event", self._on_key_press)

    def _on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            return
        from renderer import Renderer
        self.renderer = Renderer()
        self.renderer.init_gl()
        self.renderer.build_model_buffers(self.active_model)
        self._force_texture_sync()

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

    @staticmethod
    def _event_modifiers(event):
        """Extract modifier flags from a GDK event into a plain dict."""
        state = event.state
        return {
            "shift": bool(state & Gdk.ModifierType.SHIFT_MASK),
            "ctrl":  bool(state & Gdk.ModifierType.CONTROL_MASK),
            "alt":   bool(state & Gdk.ModifierType.MOD1_MASK),
        }

    def _on_button_press(self, widget, event):
        if event.button == 2 or event.button == 3:
            self._rotate_active = True
            self._last_mouse_x = event.x
            self._last_mouse_y = event.y
            return True
        elif event.button == 1:
            self._drag_active = True
            self._drag_button = 1
            self._last_drag_pixel = None
            self._drag_modifiers = self._event_modifiers(event)
            self._drag_start_mx = event.x
            self._fuzzy_drag = None
            self._handle_paint(event.x, event.y, start=True,
                               modifiers=self._drag_modifiers)
            return True
        return False

    def _on_button_release(self, widget, event):
        if event.button in (2, 3) or self._rotate_active:
            self._rotate_active = False
            return True
        elif event.button == 1:
            self._drag_active = False
            self._last_drag_pixel = None
            self._drag_modifiers = {}
            self._fuzzy_drag = None
            self._force_texture_sync()
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
        elif self._drag_active:
            if self._fuzzy_drag is not None:
                self._handle_fuzzy_drag(event.x)
            else:
                self._handle_paint(event.x, event.y, start=False,
                                   modifiers=self._drag_modifiers)
            return True
        else:
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
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        shift = event.state & Gdk.ModifierType.SHIFT_MASK

        if event.keyval == Gdk.KEY_g and not ctrl:
            self._show_grid = not self._show_grid
            self.grid_toggle.set_active(self._show_grid)
            self.gl_area.queue_render()
            return True

        if ctrl and event.keyval in (Gdk.KEY_z, Gdk.KEY_Z):
            held = {"ctrl": bool(ctrl), "shift": bool(shift)}
            if shift:
                self._gimp_redo(restore_mods=held)
            else:
                self._gimp_undo(restore_mods=held)
            return True

        if ctrl and event.keyval in (Gdk.KEY_y, Gdk.KEY_Y):
            held = {"ctrl": bool(ctrl), "shift": bool(shift)}
            self._gimp_redo(restore_mods=held)
            return True

        return False

    def _on_model_changed(self, combo):
        self.use_alex = combo.get_active() == 1
        pose_index = self.pose_combo.get_active()
        self.active_model.set_pose(pose_index)
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
        pose_index = combo.get_active()
        self.active_model.set_pose(pose_index)
        self.gl_area.make_current()
        self.renderer.build_model_buffers(self.active_model)
        self.gl_area.queue_render()

    def _on_reset_view(self, btn):
        if self.renderer:
            self.renderer.reset_camera()
            self.gl_area.queue_render()

    def _on_destroy(self, widget):
        Gtk.main_quit()

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

    # ------------------------------------------------------------------ #
    #  PDB diagnostics (runs once on first click)                          #
    # ------------------------------------------------------------------ #

    def _pdb_diagnose(self):
        if self._pdb_diagnosed:
            return
        self._pdb_diagnosed = True
        _log("=== PDB diagnostic ===")

        try:
            method = Gimp.context_get_paint_method()
            _log(f"  Active paint method: {method}")
        except Exception as exc:
            _log(f"  context_get_paint_method: {exc}")

        pdb = Gimp.get_pdb()
        for name in [
            "gimp-pencil", "gimp-paintbrush", "gimp-paintbrush-default",
            "gimp-eraser-default", "gimp-airbrush-default",
            "gimp-image-select-rectangle", "gimp-drawable-edit-fill",
            "gimp-selection-none", "gimp-displays-flush",
            "gimp-image-undo", "gimp-image-redo",
            "gimp-image-select-contiguous-color", "gimp-fuzzy-select",
            "gimp-by-color-select",
        ]:
            proc = pdb.lookup_procedure(name)
            if proc is None:
                _log(f"  [{name}] NOT FOUND")
                continue
            try:
                params = [a.get_name() for a in proc.get_arguments()]
                _log(f"  [{name}] params: {', '.join(params)}")
            except Exception as exc:
                _log(f"  [{name}] (list-params failed: {exc})")

        for attr in ("pencil", "paintbrush_default", "eraser_default"):
            fn = getattr(Gimp, attr, None)
            _log(f"  Gimp.{attr}: {'exists' if fn else 'MISSING'}")

        try:
            d = self._get_drawable()
            if d:
                _log(f"  drawable: {d.get_name()}, "
                     f"{d.get_width()}x{d.get_height()}, bpp={d.get_bpp()}")
        except Exception:
            pass

        _log("  --- undo-related PDB procedures ---")
        try:
            all_procs = pdb.get_procedures()
            if all_procs:
                for p in all_procs:
                    if "undo" in p.lower():
                        proc = pdb.lookup_procedure(p)
                        if proc:
                            try:
                                params = [a.get_name()
                                          for a in proc.get_arguments()]
                                _log(f"  [{p}] params: {', '.join(params)}")
                            except Exception:
                                _log(f"  [{p}] (params unavailable)")
                        else:
                            _log(f"  [{p}] listed but not found")
        except Exception as exc:
            _log(f"  PDB enumerate failed: {exc}")
            for name in [
                "gimp-edit-undo", "gimp-edit-redo",
                "gimp-image-undo-step", "gimp-image-redo-step",
            ]:
                proc = pdb.lookup_procedure(name)
                if proc:
                    try:
                        params = [a.get_name()
                                  for a in proc.get_arguments()]
                        _log(f"  [{name}] params: {', '.join(params)}")
                    except Exception:
                        _log(f"  [{name}] found (params unavailable)")
                else:
                    _log(f"  [{name}] NOT FOUND")

        _log("  --- Image undo attrs ---")
        for attr in dir(self.image):
            if "undo" in attr.lower():
                _log(f"  image.{attr}")

        _log("=== end ===")

    # ------------------------------------------------------------------ #
    #  Click → GIMP tool forwarding                                       #
    # ------------------------------------------------------------------ #

    def _handle_paint(self, mx, my, start=False, modifiers=None):
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
            if self._last_drag_pixel == (px, py) and not start:
                return
            self._last_drag_pixel = (px, py)
            mods = modifiers or {}
            mod_str = "+".join(k for k in ("Ctrl", "Shift", "Alt")
                               if mods.get(k.lower()))
            prefix = f"{mod_str}+" if mod_str else ""
            self.status_bar.set_text(f"{prefix}Click → ({px}, {py})")
            self._forward_click(px, py, start=start, modifiers=mods)
            self._force_texture_sync()

    def _handle_fuzzy_drag(self, mx):
        """Adjust fuzzy-select threshold based on horizontal drag distance.

        Dragging right increases the threshold (selects more),
        dragging left decreases it (selects less).  ~1 threshold unit
        per 2 screen pixels of movement.
        """
        fd = self._fuzzy_drag
        if fd is None:
            return

        dx = mx - fd["start_mx"]
        threshold = max(0.0, min(255.0, fd["base_threshold"] + dx * 0.5))

        try:
            self._do_fuzzy_select(fd["drawable"], fd["x"], fd["y"],
                                  operation=fd["operation"],
                                  threshold=threshold)
            Gimp.displays_flush()
            self._force_texture_sync()
            self.status_bar.set_text(
                f"Fuzzy Select — threshold: {threshold:.0f}")
        except Exception as exc:
            _log(f"fuzzy-drag failed: {exc}")

    # -- undo / redo -------------------------------------------------------

    def _gimp_undo(self, restore_mods=None):
        self._send_key_to_gimp("z", ctrl=True, restore_mods=restore_mods)
        GLib.timeout_add(100, self._after_undo_redo, "Undo")
        return False

    def _gimp_redo(self, restore_mods=None):
        self._send_key_to_gimp("y", ctrl=True, restore_mods=restore_mods)
        GLib.timeout_add(100, self._after_undo_redo, "Redo")
        return False

    def _after_undo_redo(self, label):
        self._force_texture_sync()
        self.status_bar.set_text(label)
        return False

    _x11_libs = None

    @classmethod
    def _get_x11_libs(cls):
        """Load libX11 and libXtst via ctypes (works inside Flatpak)."""
        if cls._x11_libs is not None:
            return cls._x11_libs

        import ctypes
        import ctypes.util

        x11_name = ctypes.util.find_library("X11") or "libX11.so.6"
        xtst_name = ctypes.util.find_library("Xtst") or "libXtst.so.6"

        libX11 = ctypes.cdll.LoadLibrary(x11_name)
        libXtst = ctypes.cdll.LoadLibrary(xtst_name)

        VP = ctypes.c_void_p
        UL = ctypes.c_ulong

        libX11.XOpenDisplay.restype = VP
        libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        libX11.XCloseDisplay.argtypes = [VP]
        libX11.XKeysymToKeycode.restype = ctypes.c_ubyte
        libX11.XKeysymToKeycode.argtypes = [VP, UL]
        libX11.XSetInputFocus.argtypes = [VP, UL, ctypes.c_int, UL]
        libX11.XGetTransientForHint.argtypes = [
            VP, UL, ctypes.POINTER(UL)]
        libX11.XGetTransientForHint.restype = ctypes.c_int
        libX11.XFlush.argtypes = [VP]
        libX11.XSync.argtypes = [VP, ctypes.c_int]

        libXtst.XTestFakeKeyEvent.argtypes = [
            VP, ctypes.c_uint, ctypes.c_int, UL]
        libXtst.XTestFakeKeyEvent.restype = ctypes.c_int

        cls._x11_libs = (libX11, libXtst)
        return cls._x11_libs

    # X11 keysym constants
    _XK_CONTROL_L = 0xffe3
    _XK_SHIFT_L = 0xffe1

    def _send_key_to_gimp(self, key_char, ctrl=False, shift=False,
                          restore_mods=None):
        """Send a synthetic key event to the GIMP image window via XTest.

        Uses ctypes to call libX11/libXtst directly — no external Python
        packages required (works inside Flatpak).
        """
        import ctypes
        import os

        try:
            libX11, libXtst = self._get_x11_libs()
        except Exception as exc:
            _log(f"X11 libs not available: {exc}")
            self.status_bar.set_text("Undo not supported (no libXtst)")
            return

        dpy = None
        try:
            display_name = os.environ.get("DISPLAY", ":0").encode()
            dpy = libX11.XOpenDisplay(display_name)
            if not dpy:
                _log("_send_key_to_gimp: XOpenDisplay failed")
                return

            our_xid = 0
            gdk_win = self.get_window()
            if gdk_win is not None:
                try:
                    our_xid = gdk_win.get_xid()
                except AttributeError:
                    try:
                        gi.require_version("GdkX11", "3.0")
                        from gi.repository import GdkX11
                        our_xid = GdkX11.X11Window.get_xid(gdk_win)
                    except Exception:
                        pass

            gimp_xid = 0
            if our_xid:
                parent_xid = ctypes.c_ulong(0)
                ok = libX11.XGetTransientForHint(
                    dpy, our_xid, ctypes.byref(parent_xid))
                if ok:
                    gimp_xid = parent_xid.value

            if not gimp_xid:
                _log("_send_key_to_gimp: no transient-for, "
                     "key goes to focused window")

            ctrl_kc = libX11.XKeysymToKeycode(dpy, self._XK_CONTROL_L)
            shift_kc = libX11.XKeysymToKeycode(dpy, self._XK_SHIFT_L)
            key_kc = libX11.XKeysymToKeycode(dpy, ord(key_char))

            # Release any physically held modifier/action keys so we
            # start from a clean slate (avoids conflicts with physical
            # key state when called from a keyboard shortcut handler).
            libXtst.XTestFakeKeyEvent(dpy, key_kc, 0, 0)
            libXtst.XTestFakeKeyEvent(dpy, ctrl_kc, 0, 0)
            libXtst.XTestFakeKeyEvent(dpy, shift_kc, 0, 0)
            libX11.XSync(dpy, 0)

            if gimp_xid:
                libX11.XSetInputFocus(dpy, gimp_xid, 1, 0)
                libX11.XSync(dpy, 0)

            # Send clean key sequence
            if ctrl:
                libXtst.XTestFakeKeyEvent(dpy, ctrl_kc, 1, 0)
            if shift:
                libXtst.XTestFakeKeyEvent(dpy, shift_kc, 1, 0)
            libXtst.XTestFakeKeyEvent(dpy, key_kc, 1, 0)
            libXtst.XTestFakeKeyEvent(dpy, key_kc, 0, 0)
            if shift:
                libXtst.XTestFakeKeyEvent(dpy, shift_kc, 0, 0)
            if ctrl:
                libXtst.XTestFakeKeyEvent(dpy, ctrl_kc, 0, 0)
            libX11.XSync(dpy, 0)

            if gimp_xid and our_xid:
                libX11.XSetInputFocus(dpy, our_xid, 1, 0)
                libX11.XSync(dpy, 0)

            if restore_mods:
                if restore_mods.get("ctrl"):
                    libXtst.XTestFakeKeyEvent(dpy, ctrl_kc, 1, 0)
                if restore_mods.get("shift"):
                    libXtst.XTestFakeKeyEvent(dpy, shift_kc, 1, 0)
                libX11.XSync(dpy, 0)

            _log(f"_send_key_to_gimp: sent {'Ctrl+' if ctrl else ''}"
                 f"{'Shift+' if shift else ''}{key_char} "
                 f"(our={our_xid:#x} gimp={gimp_xid:#x})")
        except Exception as exc:
            _log(f"_send_key_to_gimp failed: {exc}\n{traceback.format_exc()}")
        finally:
            if dpy:
                libX11.XCloseDisplay(dpy)

    def _pdb_run(self, proc_name, **kwargs):
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure(proc_name)
        if proc is None:
            raise RuntimeError(f"{proc_name} not in PDB")
        config = proc.create_config()
        for k, v in kwargs.items():
            config.set_property(k, v)
        result = proc.run(config)
        status = result.index(0)
        if status != Gimp.PDBStatusType.SUCCESS:
            raise RuntimeError(f"{proc_name} returned {status}")
        return result

    # -- tool definitions (combo index → behaviour) -----------------------

    _TOOLS = [
        # (label,       stroke_func_attr,       is_stroke_tool)
        ("Pencil",      "pencil",               True),
        ("Paintbrush",  "paintbrush_default",   True),
        ("Eraser",      "eraser_default",       True),
        ("Airbrush",    "airbrush_default",     True),
        ("Bucket Fill",  None,                   False),
        ("Color Picker", None,                   False),
        ("Fuzzy Select", None,                   False),
    ]

    def _modifiers_to_channel_op(self, modifiers, start=True):
        """Map Shift/Ctrl modifiers to a GIMP ChannelOps value.

        Matches GIMP's native convention:
          (none)       → REPLACE
          Shift        → ADD
          Ctrl         → SUBTRACT
          Shift+Ctrl   → INTERSECT
        """
        shift = modifiers.get("shift", False)
        ctrl = modifiers.get("ctrl", False)
        if shift and ctrl:
            return Gimp.ChannelOps.INTERSECT
        if shift:
            return Gimp.ChannelOps.ADD
        if ctrl:
            return Gimp.ChannelOps.SUBTRACT
        return Gimp.ChannelOps.REPLACE

    def _forward_click(self, px, py, start=True, modifiers=None):
        """Forward a click to GIMP at skin pixel (px, py) using the tool
        chosen in the toolbar dropdown.

        *start*     — True for the initial click, False for drag.
        *modifiers* — dict with 'shift', 'ctrl', 'alt' booleans.
        """
        self._pdb_diagnose()
        mods = modifiers or {}

        drawable = self._get_drawable()
        if drawable is None:
            _log("_forward_click: no drawable")
            self.status_bar.set_text("No active drawable")
            return

        w, h = drawable.get_width(), drawable.get_height()
        if px < 0 or py < 0 or px >= w or py >= h:
            return

        x, y = float(px) + 0.5, float(py) + 0.5
        tool_idx = self.tool_combo.get_active()
        tool_label, func_attr, is_stroke = self._TOOLS[tool_idx]
        _log(f"_forward_click({px},{py}) tool={tool_label} "
             f"start={start} mods={mods}")

        try:
            if is_stroke:
                if mods.get("ctrl"):
                    self._do_color_pick(drawable, x, y)
                else:
                    self._do_stroke(func_attr, drawable, x, y)
            elif tool_label == "Bucket Fill":
                if mods.get("ctrl"):
                    self._do_color_pick(drawable, x, y)
                else:
                    fill_type = (Gimp.FillType.BACKGROUND
                                 if mods.get("shift")
                                 else Gimp.FillType.FOREGROUND)
                    self._do_bucket_fill(drawable, x, y,
                                         fill_type=fill_type)
            elif tool_label == "Color Picker":
                self._do_color_pick(drawable, x, y)
            elif tool_label == "Fuzzy Select":
                op = self._modifiers_to_channel_op(mods, start=True)
                threshold = 15.0
                self._do_fuzzy_select(drawable, x, y, operation=op,
                                      threshold=threshold)
                self._fuzzy_drag = {
                    "drawable": drawable,
                    "x": x, "y": y,
                    "operation": op,
                    "base_threshold": threshold,
                    "start_mx": self._drag_start_mx,
                }
            Gimp.displays_flush()
            _log(f"  {tool_label}: OK")
        except Exception as exc:
            _log(f"  {tool_label}: FAILED – {exc}\n{traceback.format_exc()}")
            self.status_bar.set_text(f"{tool_label} failed – see log")

    # -- stroke-based tools (pencil, paintbrush, eraser, airbrush) --------

    def _do_stroke(self, func_attr, drawable, x, y):
        fn = getattr(Gimp, func_attr, None)
        if fn is None:
            raise RuntimeError(f"Gimp.{func_attr} not available")

        strokes = [x, y]

        # GI may merge (num_strokes, strokes*) into a single list param
        try:
            fn(drawable, strokes)
            return
        except TypeError:
            pass
        fn(drawable, len(strokes), strokes)

    # -- bucket fill ------------------------------------------------------

    def _do_bucket_fill(self, drawable, x, y,
                        fill_type=None):
        """Bucket fill = fuzzy-select the contiguous region, then fill it."""
        if fill_type is None:
            fill_type = Gimp.FillType.FOREGROUND
        self._do_fuzzy_select(drawable, x, y)
        Gimp.drawable_edit_fill(drawable, fill_type)
        Gimp.Selection.none(self.image)

    # -- color picker -----------------------------------------------------

    def _do_color_pick(self, drawable, x, y):
        """Pick the color at (x, y) and set it as the foreground color."""
        if _Gegl is not None:
            try:
                color = drawable.get_pixel(int(x), int(y))
                Gimp.context_set_foreground(color)
                self.status_bar.set_text(f"Picked color at ({int(x)}, {int(y)})")
                return
            except Exception as exc:
                _log(f"color_pick get_pixel: {exc}")

        self._pdb_run("gimp-color-picker",
                       drawable=drawable, x=x, y=y)

    # -- fuzzy select (magic wand) ----------------------------------------

    def _do_fuzzy_select(self, drawable, x, y,
                         operation=None, threshold=15.0):
        """Select contiguous region by color at (x, y).

        *operation*:  Gimp.ChannelOps value (REPLACE, ADD, SUBTRACT, INTERSECT).
        *threshold*:  colour-similarity tolerance (0–255).
        """
        if operation is None:
            operation = Gimp.ChannelOps.REPLACE

        # Strategy 1: direct GI method on Image
        fn = getattr(self.image, "select_contiguous_color", None)
        if fn is not None:
            try:
                Gimp.context_set_sample_threshold(threshold / 255.0)
            except Exception:
                pass
            try:
                fn(operation, drawable, x, y)
                _log(f"  fuzzy: image.select_contiguous_color"
                     f"(op={operation}, thr={threshold:.1f}) OK")
                return
            except Exception as exc:
                _log(f"  fuzzy: image.select_contiguous_color(): {exc}")

        # Strategy 2: PDB with proc.run(config)
        pdb = Gimp.get_pdb()
        candidates = [
            "gimp-image-select-contiguous-color",
            "gimp-fuzzy-select",
            "gimp-by-color-select",
        ]

        for proc_name in candidates:
            proc = pdb.lookup_procedure(proc_name)
            if proc is None:
                _log(f"  fuzzy-select: {proc_name} NOT FOUND")
                continue

            try:
                params = [a.get_name() for a in proc.get_arguments()]
                _log(f"  fuzzy-select: {proc_name} params={params}")
            except Exception:
                params = []

            config = proc.create_config()
            props = {
                "image": self.image,
                "drawable": drawable,
                "x": x,
                "y": y,
                "operation": operation,
                "threshold": threshold,
                "select-transparent": False,
                "sample-merged": False,
                "select-criterion": 0,
            }
            for k, v in props.items():
                try:
                    config.set_property(k, v)
                except Exception:
                    pass

            try:
                result = proc.run(config)
                status = result.index(0)
                _log(f"  fuzzy-select: {proc_name} thr={threshold:.1f}"
                     f" → status={status}")
                if status == Gimp.PDBStatusType.SUCCESS:
                    return
            except Exception as exc:
                _log(f"  fuzzy-select: {proc_name} run failed: {exc}")

        raise RuntimeError("No fuzzy-select procedure succeeded")

    def _poll_texture(self):
        """Periodically sync the GIMP canvas to the GL texture."""
        if self.renderer is None:
            return True
        if not self.get_visible():
            return True

        try:
            self._sync_texture()
            self._sync_selection()
        except Exception as exc:
            _log(f"poll_texture error: {exc}\n{traceback.format_exc()}")
        return True

    def _force_texture_sync(self):
        self._last_texture_hash = None
        self._sync_texture()

    def _upload_pixels(self, pixel_data, width, height, read_bpp):
        """Convert to RGBA if needed, hash-check, and upload to GL."""
        if read_bpp == 3:
            rgba = bytearray(width * height * 4)
            for i in range(width * height):
                rgba[i * 4]     = pixel_data[i * 3]
                rgba[i * 4 + 1] = pixel_data[i * 3 + 1]
                rgba[i * 4 + 2] = pixel_data[i * 3 + 2]
                rgba[i * 4 + 3] = 255
            pixel_data = bytes(rgba)

        h = hashlib.md5(pixel_data).digest()
        if h == self._last_texture_hash:
            return
        self._last_texture_hash = h

        self.gl_area.make_current()
        self.renderer.update_texture(pixel_data, width, height)
        self.gl_area.queue_render()

    def _sync_texture(self):
        width = self.image.get_width()
        height = self.image.get_height()
        if width == 0 or height == 0:
            return

        layers = self.image.get_layers()
        visible = [l for l in layers if l.get_visible()]

        if not visible:
            return

        if len(visible) == 1:
            self._sync_texture_from_drawable(visible[0], width, height)
            return

        if _Gegl is not None:
            try:
                self._sync_texture_composite(visible, width, height)
                return
            except Exception as exc:
                _log(f"composite failed: {exc}\n{traceback.format_exc()}")

        self._sync_texture_from_drawable(visible[0], width, height)

    def _sync_texture_composite(self, visible_layers, width, height):
        """Alpha-composite all visible layers (bottom-to-top) into one RGBA buffer."""
        composite = bytearray(width * height * 4)

        for layer in reversed(visible_layers):
            lw = layer.get_width()
            lh = layer.get_height()

            try:
                off = layer.get_offsets()
                if isinstance(off, (list, tuple)):
                    if len(off) == 3:
                        _, offx, offy = off
                    else:
                        offx, offy = off[0], off[1]
                else:
                    offx, offy = 0, 0
            except Exception:
                offx, offy = 0, 0

            opacity = layer.get_opacity() / 100.0

            buf = layer.get_buffer()
            rect = _Gegl.Rectangle.new(0, 0, lw, lh)
            data = buf.get(rect, 1.0, "R'G'B'A u8", _Gegl.AbyssPolicy.NONE)
            if data is None or len(data) == 0:
                continue
            src = bytes(data)

            for ly in range(lh):
                dy = ly + offy
                if dy < 0 or dy >= height:
                    continue
                for lx in range(lw):
                    dx = lx + offx
                    if dx < 0 or dx >= width:
                        continue

                    si = (ly * lw + lx) * 4
                    di = (dy * width + dx) * 4
                    sa = (src[si + 3] / 255.0) * opacity
                    if sa < 0.004:
                        continue

                    da = composite[di + 3] / 255.0
                    oa = sa + da * (1.0 - sa)
                    if oa > 0:
                        inv = da * (1.0 - sa)
                        composite[di]     = min(255, int((src[si]     * sa + composite[di]     * inv) / oa))
                        composite[di + 1] = min(255, int((src[si + 1] * sa + composite[di + 1] * inv) / oa))
                        composite[di + 2] = min(255, int((src[si + 2] * sa + composite[di + 2] * inv) / oa))
                        composite[di + 3] = min(255, int(oa * 255))

        self._upload_pixels(bytes(composite), width, height, 4)

    def _sync_texture_from_drawable(self, drawable, width, height):
        """Read pixels from a single drawable (fallback)."""
        if _Gegl is not None:
            try:
                buf = drawable.get_buffer()
                rect = _Gegl.Rectangle.new(0, 0, width, height)
                data = buf.get(rect, 1.0, "R'G'B'A u8", _Gegl.AbyssPolicy.NONE)
                if data is not None and len(data) > 0:
                    self._upload_pixels(bytes(data), width, height, 4)
                    return
            except Exception as exc:
                _log(f"Gegl strategy failed: {exc}\n{traceback.format_exc()}")

        try:
            self._sync_texture_get_pixel(drawable, width, height)
            return
        except Exception as exc:
            _log(f"get_pixel strategy failed: {exc}\n{traceback.format_exc()}")

        try:
            self._sync_texture_pdb(drawable, width, height)
        except Exception as exc:
            _log(f"PDB strategy failed: {exc}\n{traceback.format_exc()}")

    def _sync_texture_get_pixel(self, drawable, width, height):
        """Read pixels one-by-one via Gimp.Drawable.get_pixel / Gegl.Color."""
        pixels = bytearray(width * height * 4)
        for y in range(height):
            for x in range(width):
                color = drawable.get_pixel(x, y)
                rgba = color.get_rgba()
                idx = (y * width + x) * 4
                pixels[idx]     = max(0, min(255, int(rgba[0] * 255)))
                pixels[idx + 1] = max(0, min(255, int(rgba[1] * 255)))
                pixels[idx + 2] = max(0, min(255, int(rgba[2] * 255)))
                pixels[idx + 3] = max(0, min(255, int(rgba[3] * 255)))

        self._upload_pixels(bytes(pixels), width, height, 4)

    def _sync_texture_pdb(self, drawable, width, height):
        """Last-resort: use PDB gimp-drawable-get-pixel."""
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure("gimp-drawable-get-pixel")
        if proc is None:
            raise RuntimeError("gimp-drawable-get-pixel not found")

        pixels = bytearray(width * height * 4)
        for y in range(height):
            for x in range(width):
                config = proc.create_config()
                config.set_property("drawable", drawable)
                config.set_property("x-coord", x)
                config.set_property("y-coord", y)
                result = proc.run(config)
                if result.index(0) == Gimp.PDBStatusType.SUCCESS:
                    num_channels = result.index(1)
                    pixel = result.index(2)
                    idx = (y * width + x) * 4
                    pixels[idx]     = pixel[0] if num_channels > 0 else 0
                    pixels[idx + 1] = pixel[1] if num_channels > 1 else 0
                    pixels[idx + 2] = pixel[2] if num_channels > 2 else 0
                    pixels[idx + 3] = pixel[3] if num_channels > 3 else 255

        self._upload_pixels(bytes(pixels), width, height, 4)

    def _sync_selection(self):
        """Read the GIMP selection mask and update the selection overlay texture."""
        if not self._show_selection_overlay or self.renderer is None:
            return
        try:
            is_empty = Gimp.Selection.is_empty(self.image)
            if is_empty:
                if self.has_selection_cached:
                    self.renderer.update_selection_texture(None, 0, 0)
                    self._last_selection_hash = None
                    self.has_selection_cached = False
                    self.gl_area.queue_render()
                return

            width = self.image.get_width()
            height = self.image.get_height()

            channel = self.image.get_selection()
            if channel is None:
                return

            if _Gegl is None:
                return

            buf = channel.get_buffer()
            rect = _Gegl.Rectangle.new(0, 0, width, height)
            data = buf.get(rect, 1.0, "Y u8", _Gegl.AbyssPolicy.NONE)

            if data is None:
                return

            mask_data = bytes(data)
            h = hashlib.md5(mask_data).digest()
            if h == self._last_selection_hash:
                return
            self._last_selection_hash = h
            self.has_selection_cached = True

            self.gl_area.make_current()
            self.renderer.update_selection_texture(mask_data, width, height)
            self.gl_area.queue_render()
        except Exception as exc:
            _log(f"sync_selection error: {exc}\n{traceback.format_exc()}")


class MinecraftSkin3D(Gimp.PlugIn):
    """GIMP 3 plugin registration."""

    def do_set_i18n(self, name):
        return False

    def do_query_procedures(self):
        return ["minecraft-skin-3d-preview"]

    def do_create_procedure(self, name):
        if name == "minecraft-skin-3d-preview":
            procedure = Gimp.ImageProcedure.new(
                self,
                name,
                Gimp.PDBProcType.PLUGIN,
                self._run,
                None,
            )
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.DRAWABLE
            )
            procedure.set_menu_label("Minecraft Skin 3D Preview")
            procedure.set_attribution(
                "GNUMC",
                "GNUMC",
                "2026",
            )
            procedure.add_menu_path("<Image>/Filters/Map")
            return procedure
        return None

    def _run(self, procedure, run_mode, image, drawables, config, data):
        if not drawables:
            return procedure.new_return_values(
                Gimp.PDBStatusType.CALLING_ERROR, GLib.Error()
            )

        _lazy_import()

        drawable = drawables[0]

        GimpUi.init("minecraft-skin-3d")

        win = MinecraftSkin3DWindow(image, drawable)
        win.show_all()

        Gtk.main()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(MinecraftSkin3D.__gtype__, sys.argv)
