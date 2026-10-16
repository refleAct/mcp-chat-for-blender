---
name: godot-export
description: Godot 4 GLTF/GLB export with embedded materials and CollisionShape hints.
domain: pipeline_gamedev
triggers: 고도, godot, 고도 익스포트, godot export, glb
---

# Godot Export
Exports standard GLB with -col and -navmesh suffixes for Godot import.

## Verified bpy Recipe
```python
import bpy

filepath = bpy.path.abspath("//godot_asset.glb")
bpy.ops.export_scene.gltf(
    filepath=filepath,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
```
