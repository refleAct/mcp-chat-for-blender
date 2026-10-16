---
name: blender-toolkit
description: Core geometry creation, mesh primitives, and modifier utilities.
domain: hard_surface
triggers: toolkit, 프리미티브 생성, 블렌더 툴킷, create cube, primitive
---

# Blender Toolkit
Creates clean parametric primitives and modifiers.

## Verified bpy Recipe
```python
import bpy

def create_blockout_box(size=(2, 2, 2), loc=(0, 0, 1)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    box = bpy.context.active_object
    box.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return box
```
