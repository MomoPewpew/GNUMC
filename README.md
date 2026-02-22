# GNUMC - Minecraft Skin 3D Editor for GIMP

A GIMP 3 plugin that provides a live 3D preview of Minecraft player skins.
Edit your skin in GIMP's 2D editor and see the changes in real time on a
rotatable 3D player model — or paint, select, and fill directly on the 3D
view using your GIMP tools.

## Features

- **Live 3D Preview**: See your 64×64 skin texture mapped onto a Minecraft
  player model in real time as you edit in the 2D canvas.
- **Tool Forwarding**: Use Pencil, Paintbrush, Eraser, Airbrush, Bucket Fill,
  Color Picker, or Fuzzy Select directly on the 3D model. Clicks are forwarded
  to GIMP at the corresponding texture coordinate.
- **Click Modifiers**: Shift, Ctrl, and Alt modify tool behavior just like in
  GIMP (e.g. Shift+click with Fuzzy Select to add to selection, Ctrl+click
  with a paint tool to pick a color).
- **Fuzzy Select Drag**: Click and drag horizontally with Fuzzy Select to
  adjust the selection threshold in real time, matching GIMP's native behavior.
- **Composite Layer Rendering**: The 3D preview shows all visible layers
  composited together, not just the active layer.
- **Undo / Redo**: Undo and redo via toolbar buttons or Ctrl+Z / Ctrl+Y
  hotkeys, forwarded directly to GIMP.
- **Steve and Alex Models**: Toggle between classic (4px arms) and slim (3px
  arms) models.
- **Overlay Toggle**: Show or hide the outer (overlay) skin layer.
- **Pose Controls**: Preview your skin in standing, walking, or T-pose.
- **Pixel Grid Overlay**: Toggle a grid on the 3D model to see individual
  pixel boundaries (G key).
- **Hover Highlight**: Marching-ants highlight around the pixel under the
  cursor, matching GIMP's selection style.
- **Selection Visualization**: GIMP selections are shown as a marching-ants
  overlay on the 3D model.
- **Hover Coordinates**: The status bar shows which texture pixel your cursor
  is over.

## Requirements

- **GIMP 3.0+**
- OpenGL 3.3+ capable GPU
- X11 display (Wayland via XWayland works)

PyOpenGL is bundled with the plugin — no separate installation needed.

## Installation

### Quick install (recommended)

Download the [latest release](https://github.com/MomoPewpew/GNUMC/releases)
or clone the repository, then run:

```bash
./install.sh
```

The script automatically detects your GIMP plug-ins directory (standard
installs, Flatpak, and Snap), copies the plugin files, and sets permissions.
You can override the target with:

```bash
GIMP_PLUGIN_DIR=/custom/path ./install.sh
```

To remove the plugin:

```bash
./install.sh --uninstall
```

### Manual installation

1. Locate your GIMP 3 plug-ins directory:
   - Linux: `~/.config/GIMP/3.0/plug-ins/`
   - Flatpak: `~/.var/app/org.gimp.GIMP/config/GIMP/3.0/plug-ins/`
   - macOS: `~/Library/Application Support/GIMP/3.0/plug-ins/`
   - Windows: `%APPDATA%\GIMP\3.0\plug-ins\`

2. Copy the `minecraft-skin-3d` folder into the plug-ins directory:

```bash
cp -r minecraft-skin-3d ~/.config/GIMP/3.0/plug-ins/
```

3. Make the main script executable (Linux/macOS):

```bash
chmod +x ~/.config/GIMP/3.0/plug-ins/minecraft-skin-3d/minecraft-skin-3d.py
```

4. Restart GIMP. The plugin appears under **Filters > Map >
   Minecraft Skin 3D Preview**.

### Flatpak extension

If you installed GIMP as a Flatpak and want to distribute or install the
plugin as a proper Flatpak extension, see the `flatpak/` directory for
the manifest and AppStream metadata. To build and install locally:

```bash
cd flatpak
flatpak-builder --force-clean --disable-rofiles-fuse --repo=repo \
    _build org.gimp.GIMP.Plugin.MinecraftSkin3D.json
flatpak build-bundle --runtime repo \
    org.gimp.GIMP.Plugin.MinecraftSkin3D.flatpak \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    org.gimp.GIMP.Plugin.MinecraftSkin3D 3
flatpak install --user org.gimp.GIMP.Plugin.MinecraftSkin3D.flatpak
```

## Usage

1. Open a 64×64 PNG skin file in GIMP (or create a new 64×64 image).
2. Go to **Filters > Map > Minecraft Skin 3D Preview**.
3. A 3D preview window opens:

| Action | Effect |
|---|---|
| **Left-click / drag** | Use the selected tool on the model |
| **Middle-drag** or **Right-drag** | Rotate the camera |
| **Scroll wheel** | Zoom in / out |
| **Shift / Ctrl / Alt + click** | Tool modifiers (add to selection, pick color, etc.) |
| **Ctrl+Z** | Undo |
| **Ctrl+Y** or **Ctrl+Shift+Z** | Redo |
| **G** | Toggle pixel grid overlay |

4. Use the toolbar dropdown to switch between tools (Pencil, Paintbrush,
   Eraser, Airbrush, Bucket Fill, Color Picker, Fuzzy Select).
5. Edits in the GIMP 2D canvas are reflected live in the 3D preview and
   vice versa.

## Standalone Preview (no GIMP required)

You can preview a skin in 3D without launching GIMP:

```bash
# Generated test texture (works with no arguments)
python standalone_preview.py

# Load a real skin file
python standalone_preview.py path/to/skin.png

# Auto-reload when the file changes on disk
python standalone_preview.py --watch path/to/skin.png
```

## Development

```bash
# Install dev/test dependencies
pip install -r requirements-dev.txt

# Run the test suite (74 tests, no GIMP or display needed)
make test          # or: python -m pytest tests/ -v

# Install the plugin into GIMP's plug-ins directory
make install

# Remove it
make uninstall

# Launch standalone preview
make preview                          # test texture
make preview SKIN=path/to/skin.png    # real skin

# Clean up __pycache__
make clean
```

## Architecture

```
minecraft-skin-3d/
    minecraft-skin-3d.py   # Plugin entry point, GTK window, GIMP integration
    model.py               # Player model geometry and UV mapping
    renderer.py            # OpenGL rendering, shaders, camera
    interaction.py         # Ray casting, UV mapping, 3D-to-2D interaction
    mathutil.py            # Shared linear algebra (no external deps)
    shaders/
        vertex.glsl        # Vertex shader
        fragment.glsl      # Fragment shader with lighting, grid, selection
        selection.glsl     # Selection overlay shader (reserved)
    vendor/
        OpenGL/            # Vendored PyOpenGL (no pip install needed)
standalone_preview.py      # Standalone viewer (no GIMP required)
tests/                     # Unit tests (pytest)
flatpak/                   # Flatpak extension manifest and metainfo
Makefile                   # Build/test/install targets
install.sh                 # Install/uninstall script
requirements-dev.txt       # Dev dependencies (pytest + PyOpenGL)
```

## License

GPL-3.0 — compatible with GIMP's license.
