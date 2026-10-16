---
name: dynamic-full-loop
description: Speed-ramped loop showing all sides with fast transitions.
domain: animation
triggers: 다이내믹 루프, dynamic loop, whip transition, 루프 회전
---

# Dynamic Full Loop
Fast-slow-fast easing curve for dynamic social media product loops.

## Verified bpy Recipe
```python
import bpy, math

obj = bpy.context.active_object
if obj:
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 90
    obj.rotation_euler = (0, 0, 0)
    obj.keyframe_insert(data_path="rotation_euler", frame=1)
    obj.rotation_euler = (0, 0, math.radians(360))
    obj.keyframe_insert(data_path="rotation_euler", frame=90)
    # Apply Bezier S-curve
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'
print("Configured dynamic full loop.")
```
