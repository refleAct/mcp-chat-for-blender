---
name: texture-baking
description: Bakes high-poly sculpt details (Normal, Ambient Occlusion, Curvature) onto low-poly UV unwrapped meshes.
domain: materials
triggers: 베이킹, 텍스처 베이킹, texture baking, bake normal, high to low bake, 노멀맵 굽기, bake ao
---

# Texture Baking (High-Poly to Low-Poly)
Bakes tangent-space normal maps and ambient occlusion maps from high-resolution geometry onto low-poly game models.

## Verified bpy Recipe
```python
import bpy

def bake_high_to_low(high_obj, low_obj, bake_type='NORMAL', img_name="Baked_Normal_Map", res=2048):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.bake_type = bake_type
    
    image = bpy.data.images.new(name=img_name, width=res, height=res, alpha=False, is_float=False)
    image.colorspace_settings.name = 'Non-Color' if bake_type == 'NORMAL' else 'sRGB'

    if not low_obj.data.materials:
        mat = bpy.data.materials.new(name=f"{low_obj.name}_BakeMat")
        mat.use_nodes = True
        low_obj.data.materials.append(mat)
    else:
        mat = low_obj.data.materials[0]

    nodes = mat.node_tree.nodes
    bake_node = nodes.new('ShaderNodeTexImage')
    bake_node.image = image
    nodes.active = bake_node

    bpy.ops.object.select_all(action='DESELECT')
    high_obj.select_set(True)
    low_obj.select_set(True)
    bpy.context.view_layer.objects.active = low_obj

    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = 0.05
    bpy.context.scene.render.bake.max_ray_distance = 0.1
    bpy.ops.object.bake(type=bake_type)
    print(f"Baked {bake_type} map to {image.name}")
```
