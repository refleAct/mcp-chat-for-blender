---
name: unreal-export
description: Unreal Engine specific FBX export with 0.01 scale, Z-Up, UCX collision, and LOD groups.
domain: pipeline_gamedev
triggers: 언리얼, UE5, UE4, 언리얼 익스포트, unreal export, ue fbx
---

# Unreal Export
Exports UE-ready FBX with centimeters scale awareness and correct axis forward.

## Verified bpy Recipe
```python
import bpy, os

filepath = bpy.path.abspath("//export_ue5_asset.fbx")
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=True,
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',
    axis_up='Y',
    bake_space_transform=True,
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    mesh_smooth_type='FACE'
)
print(f"Exported to Unreal: {filepath}")
```
