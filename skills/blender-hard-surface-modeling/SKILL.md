---
name: blender-hard-surface-modeling
description: Subdivision surface, edge creasing, and non-destructive beveling workflow.
domain: hard_surface
triggers: 하드서페이스 모델링, hard surface modeling, composio hard surface
---

# Blender Hard Surface Modeling
Clean quad edge loops with Bevel modifier and auto-smoothed vertex normals.

## Verified bpy Recipe
```python
import bpy

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
    bev.width = 0.02
    bev.segments = 3
    bev.limit_method = 'ANGLE'
    obj.data.use_auto_smooth = True
```
