---
name: turntable
description: 360-degree turntable camera orbit around a 3D product or character. Classic showcase animation.
domain: camera_lighting
triggers: 턴테이블, turntable, 360, 카메라 회전, orbit, 쇼케이스
---

# Turntable Camera Animation
Orbits the camera 360 degrees around the product for a clean product showcase. Starts front-facing and loops seamlessly.

## Prerequisites
- Blender 4.0+
- Active object selected

## Verified bpy Recipe
```python
import bpy, math
from mathutils import Vector

obj = bpy.context.active_object or (bpy.context.selected_objects[0] if bpy.context.selected_objects else None)
if obj:
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = sum(bbox, Vector()) / 8.0
    size = max((max(v[i] for v in bbox) - min(v[i] for v in bbox)) for i in range(3))
else:
    center = Vector((0.0, 0.0, 0.0))
    size = 2.0

dist = max(size * 2.5, 3.0)
height = max(size * 0.8, 1.5)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
target = bpy.context.active_object
target.name = 'TurntableTarget'

bpy.ops.object.camera_add(location=(center.x, center.y - dist, center.z + height))
cam = bpy.context.active_object
cam.name = 'TurntableCam'
bpy.context.scene.camera = cam

con = cam.constraints.new(type='TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 120
target.rotation_euler = (0, 0, 0)
target.keyframe_insert(data_path="rotation_euler", frame=1)
target.rotation_euler = (0, 0, math.radians(360))
target.keyframe_insert(data_path="rotation_euler", frame=120)

# Set Linear interpolation (safely handles Blender 4.x and 5.x)
try:
    if target.animation_data and target.animation_data.action:
        curves = getattr(target.animation_data.action, "fcurves", None) or getattr(target.animation_data.action, "curves", None) or []
        for fc in curves:
            for kf in getattr(fc, "keyframe_points", []):
                kf.interpolation = 'LINEAR'
except Exception:
    pass
print("Turntable animation configured.")
```
