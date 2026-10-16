---
name: crane-shot
description: Low to high vertical camera reveal sweeping from base to top.
domain: camera_lighting
triggers: 크레인, crane, crane shot, 상승 샷, 앙각에서 조감
---

# Crane Shot
Moves camera from ground-level angle up to high 45-degree isometric view.

## Verified bpy Recipe
```python
import bpy

bpy.ops.object.camera_add(location=(0, -4, 0.2))
cam = bpy.context.active_object
bpy.context.scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 1))
target = bpy.context.active_object
con = cam.constraints.new(type='TRACK_TO')
con.target = target

cam.location = (0, -3.5, 0.3)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (2, -3.5, 4.0)
cam.keyframe_insert(data_path="location", frame=120)
print("Configured crane elevation shot.")
```
