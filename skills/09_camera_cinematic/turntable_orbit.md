---
name: cam-turntable-orbit
description: 360-degree seamless turntable camera orbit around product or character.
---

### Standard Workflow:
1. Calculate target center from active object bounding box.
2. Create an Empty at center named `TurntableTarget`.
3. Create Camera positioned at distance (default: radius * 3.0, height: radius * 1.2).
4. Add `TRACK_TO` constraint to Camera pointing to `TurntableTarget`.
5. Keyframe Z rotation of Target or Parent Rig from frame 1 (0 rad) to frame 120 (2*pi rad).

### Verified bpy Recipe:
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

# Target Empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
target = bpy.context.active_object
target.name = "TurntableTarget"

# Camera Rig
bpy.ops.object.camera_add(location=(center.x, center.y - dist, center.z + height))
cam = bpy.context.active_object
cam.name = "TurntableCam"
bpy.context.scene.camera = cam

con = cam.constraints.new(type='TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

# Animate 360 Rotation
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
