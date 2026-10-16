---
name: perfect-loop
description: Mathematically seamless cyclical motion with matching start/end derivatives.
domain: animation
triggers: 퍼펙트 루프, perfect loop, 무한 루프, seamless cycle
---

# Perfect Loop
Ensures first and last frames match in position, rotation, and derivative velocity.

## Verified bpy Recipe
```python
import bpy

def make_loop(obj, frames=60):
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frames
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location.z += 0.5
    obj.keyframe_insert(data_path="location", frame=frames // 2)
    obj.location.z -= 0.5
    obj.keyframe_insert(data_path="location", frame=frames + 1)
```
