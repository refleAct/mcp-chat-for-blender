---
name: light-studio-three-point
description: Automatic 3-point studio lighting rig (Key, Fill, Rim) calibrated to asset bounding box.
---

### Standard Workflow:
1. Key Light: 45 degrees left and up, high intensity, warm color (5500K).
2. Fill Light: 45 degrees right, 50% Key power, cooler tone (6500K).
3. Rim/Back Light: Directly behind asset, elevated, sharp edge separation.

### Verified bpy Recipe:
```python
import bpy, math
from mathutils import Vector

obj = bpy.context.active_object
if obj:
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = sum(bbox, Vector()) / 8.0
    size = max((max(v[i] for v in bbox) - min(v[i] for v in bbox)) for i in range(3))
else:
    center = Vector((0.0, 0.0, 0.0))
    size = 2.0

col = bpy.data.collections.get("Studio_Lighting") or bpy.data.collections.new("Studio_Lighting")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)

dist = size * 2.2
base_power = max(size * 150.0, 300.0)

lights_data = [
    ("Key_Light", (center.x - dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.8), base_power, (1.0, 0.95, 0.9)),
    ("Fill_Light", (center.x + dist * 0.8, center.y - dist * 0.5, center.z + dist * 0.4), base_power * 0.4, (0.85, 0.9, 1.0)),
    ("Rim_Light", (center.x + dist * 0.3, center.y + dist * 0.9, center.z + dist * 1.1), base_power * 1.2, (1.0, 1.0, 1.0))
]

for name, pos, power, color in lights_data:
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = power
    light_data.color = color
    light_data.size = size * 0.5
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    light_obj.location = pos
    col.objects.link(light_obj)
    
    # Track to center
    con = light_obj.constraints.new(type='TRACK_TO')
    con.target = obj
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
```
