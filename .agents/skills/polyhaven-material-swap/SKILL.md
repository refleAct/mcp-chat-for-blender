---
name: polyhaven-material-swap
description: Automated replacement and testing of PBR texture surfaces.
domain: materials
triggers: polyhaven, 재질 교체, material swap, cc0 swap, pbr swap
---

# PolyHaven Material Swap
Swaps active material with CC0 PBR node graph.

## Verified bpy Recipe
```python
import bpy

def apply_pbr_mat(obj, name, color=(0.8, 0.8, 0.8, 1.0), roughness=0.3, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    print(f"Applied material {name} to {obj.name}")
```
