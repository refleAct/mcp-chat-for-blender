---
name: dolly-rotate
description: Camera moves forward along a curved path while rotating around target.
domain: camera_lighting
triggers: 돌리, dolly, dolly rotate, 스위핑, 회전 이동
---

# Dolly Rotate
Camera translates forward while simultaneously rotating to sweep past the product.

## Verified bpy Recipe
```python
import bpy, math
from mathutils import Vector

target_pos = Vector((0, 0, 1))
bpy.ops.object.camera_add(location=(-3, -4, 2))
cam = bpy.context.active_object
bpy.context.scene.camera = cam

con = cam.constraints.new(type='TRACK_TO')
bpy.ops.object.empty_add(type='PLAIN_AXES', location=target_pos)
t_empty = bpy.context.active_object
con.target = t_empty

cam.location = (-4, -4, 2.5)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (2, -2.5, 0.8)
cam.keyframe_insert(data_path="location", frame=100)
print("Configured dolly rotate shot.")
```
