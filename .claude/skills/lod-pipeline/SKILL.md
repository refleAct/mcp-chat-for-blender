---
name: lod-pipeline
description: Automated LOD0 (100%), LOD1 (50%), LOD2 (25%), LOD3 (12%) decimation chain.
domain: pipeline_gamedev
triggers: LOD, lod, lod pipeline, 레벨오브디테일, decimate lod
---

# LOD Pipeline
Creates sequential LOD meshes with Decimate modifier and standardized names.

## Verified bpy Recipe
```python
import bpy

base = bpy.context.active_object
clean = base.name.split("_LOD")[0]
base.name = f"{clean}_LOD0"

for tag, ratio in [("LOD1", 0.5), ("LOD2", 0.25), ("LOD3", 0.12)]:
    mesh = base.data.copy()
    obj = bpy.data.objects.new(f"{clean}_{tag}", mesh)
    obj.matrix_world = base.matrix_world.copy()
    bpy.context.collection.objects.link(obj)
    mod = obj.modifiers.new(name="LOD_Decimate", type='DECIMATE')
    mod.ratio = ratio
    obj.hide_viewport = True
print("Created LOD0-LOD3 chain.")
```
