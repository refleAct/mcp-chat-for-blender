---
name: slow-zoom
description: Cinematic push-in toward a hero detail for dramatic product reveal.
domain: camera_lighting
triggers: 줌인, slow zoom, 클로즈업, zoom in, reveal, 초점
---

# Slow Zoom In Animation
Slow, cinematic push-in toward hero detail with subtle focal shift.

## Verified bpy Recipe
```python
import bpy
from mathutils import Vector

cam = bpy.context.scene.camera
if not cam:
    bpy.ops.object.camera_add(location=(0, -5, 2))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 96

# Animate Focal Length or Distance
cam.data.lens = 45.0
cam.data.keyframe_insert(data_path="lens", frame=1)
cam.data.lens = 75.0
cam.data.keyframe_insert(data_path="lens", frame=96)
print("Configured cinematic slow zoom.")
```
