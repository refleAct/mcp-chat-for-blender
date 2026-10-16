---
name: retopology
description: Converts high-poly sculpts into clean quad-dominant low-poly game models.
domain: character
triggers: 리토폴로지, retopology, 로우폴 변환, 쿼드 리토폴
---

# Retopology Workflow
Shrinkwrap snapping setup for manual or semi-automated quad retopology.

## Verified bpy Recipe
```python
import bpy

high_poly = bpy.context.active_object
if high_poly:
    # Create retopo plane
    bpy.ops.mesh.primitive_plane_add(size=0.2, location=high_poly.location)
    retopo = bpy.context.active_object
    retopo.name = f"{high_poly.name}_Retopo"
    
    mod = retopo.modifiers.new(name="Shrinkwrap", type='SHRINKWRAP')
    mod.target = high_poly
    mod.wrap_method = 'TARGET_PROJECT'
    retopo.show_in_front = True
```
