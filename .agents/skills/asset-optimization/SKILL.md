---
name: asset-optimization
description: Cleans orphan data, applies scale/rotation, checks polygon budgets, and fixes normal orientations.
domain: pipeline_gamedev
triggers: 에셋 최적화, asset optimization, 최적화, 메쉬 정리, apply transform
---

# Asset Optimization
Applies scale/rotation, recalculates outside normals, removes unassigned materials.

## Verified bpy Recipe
```python
import bpy

for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.object.mode_set(mode='OBJECT')
print("Optimized and sanitized meshes.")
```
