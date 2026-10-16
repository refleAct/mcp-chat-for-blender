---
name: unity-export
description: Unity specific FBX export with -180 rotation compensation and Y-up coordinate.
domain: pipeline_gamedev
triggers: 유니티, unity, 유니티 익스포트, unity export
---

# Unity Export
Exports FBX properly oriented for Unity's coordinate system.

## Verified bpy Recipe
```python
import bpy

filepath = bpy.path.abspath("//unity_asset.fbx")
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=True,
    axis_forward='Z',
    axis_up='Y',
    apply_scale_options='FBX_SCALE_ALL'
)
```
