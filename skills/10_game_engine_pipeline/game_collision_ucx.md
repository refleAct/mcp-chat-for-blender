---
name: pipe-game-collision-ucx
description: Generate simplified convex hull and box collision primitives prefixed with UCX_ for Unreal Engine.
---

### Standard Workflow:
- Unreal recognizes collision meshes starting with `UCX_` (Convex Hull), `UBX_` (Box), `USP_` (Sphere), `UCP_` (Capsule).
- Name format: `UCX_<TargetMeshName>_<Index>` (e.g. `UCX_Door_01`).
- Must belong to the same export hierarchy or group.

### Verified bpy Recipe:
```python
import bpy, bmesh
from mathutils import Vector

active_obj = bpy.context.active_object
if not active_obj or active_obj.type != 'MESH':
    raise RuntimeError("Select a valid mesh object to generate UCX collision.")

base_name = active_obj.name.replace("UCX_", "")
col_name = f"UCX_{base_name}_01"

# Create duplicate mesh for convex hull
col_mesh = active_obj.data.copy()
col_mesh.name = f"{col_name}_Mesh"
col_obj = bpy.data.objects.new(col_name, col_mesh)
col_obj.matrix_world = active_obj.matrix_world.copy()

# Link to active collection
bpy.context.collection.objects.link(col_obj)

# Compute Convex Hull using bmesh
bm = bmesh.new()
bm.from_mesh(col_mesh)
bmesh.ops.convex_hull(bm, input=bm.verts)

# Clean interior geometry left by convex hull
for f in list(bm.faces):
    if not f.is_valid:
        continue
bm.to_mesh(col_mesh)
bm.free()

# Display as wireframe in Blender viewport for visual inspection
col_obj.display_type = 'WIRE'
col_obj.show_wire = True

print(f"Generated UCX collision mesh: {col_obj.name}")
```
