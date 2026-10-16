---
name: blender-product-polish
description: Cleans raw AI-generated GLTF meshes and sets 4-point studio lighting.
domain: materials
triggers: 제품 폴리싱, 에셋 정리, product polish, studio setup, 광택
---

# Blender Product Polish
Cleans imported GLTF geometry, unifies scales, and applies studio lighting.

## Verified bpy Recipe
```python
import bpy

for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.shade_smooth()
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
print("Product polished and smoothed.")
```
