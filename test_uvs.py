import sys
import os

# Add the plugin directory to sys.path
sys.path.insert(0, os.path.join(os.getcwd(), "minecraft-skin-3d"))

from model import BoxPart

def test_uvs():
    # A head-like box at (0,0,0) with size (8,8,8) and UV (0,0)
    # Minecraft head unwrap:
    # Right: (0, 8) to (8, 16)
    # Front: (8, 8) to (16, 16)
    # Left:  (16, 8) to (24, 16)
    # Back:  (24, 8) to (32, 16)
    # Top:   (8, 0) to (16, 8)
    # Bottom:(16, 0) to (24, 8)
    head = BoxPart("head", (0, 0, 0), (8, 8, 8), (0, 0))
    
    quads = head.get_face_quads()
    
    for face, verts, uvs in quads:
        print(f"Face: {face}")
        for i in range(4):
            print(f"  v{i}: {verts[i]} -> uv{i}: {uvs[i]}")
        print()

if __name__ == "__main__":
    test_uvs()
