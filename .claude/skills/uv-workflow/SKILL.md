---
name: uv-workflow
description: Marks seams on hard edges, unwraps angle-based islands, and packs UVs.
domain: materials
triggers: UV, uv workflow, uv 언랩, uv 패킹, seam
---

# UV Workflow
Marks seams along sharp angles (>35 deg) and runs Angle-Based unwrap.

## Verified bpy Recipe
```python
import bpy

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.edges_select_sharp(sharpness=0.61) # ~35 deg
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.02)
    bpy.ops.uv.pack_islands(margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
print(f"Unwrapped UVs for {obj.name}")
```
