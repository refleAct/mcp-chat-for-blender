---
name: hard-surface-booleans
description: Non-destructive boolean cuts with Bevel modifier and Weighted Normal smoothing.
---

### Standard Workflow:
1. Base mesh gets `BOOLEAN` modifier targeting cutter mesh.
2. Add `BEVEL` modifier (Limit: Weight or Angle, Width: 0.02m, Segments: 2~3).
3. Add `WEIGHTED_NORMAL` modifier with `keep_sharp=True` for pristine CAD-like reflections.
4. If Bool Tool addon is active, use its fast shortcut operator.

### Verified bpy Recipe:
```python
import bpy

target = bpy.context.active_object
selected = [o for o in bpy.context.selected_objects if o != target]

if not target or not selected:
    raise RuntimeError("Select the Cutter object first, then the Target object last.")

cutter = selected[0]

# Check if Bool Tool addon is available
try:
    bpy.ops.object.booltool_auto_difference()
    print("Executed via Bool Tool addon operator.")
except Exception:
    # Fallback to standard non-destructive modifier stack
    bool_mod = target.modifiers.new(name=f"Bool_{cutter.name}", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    bool_mod.solver = 'EXACT'
    
    # Hide cutter from render and viewport
    cutter.display_type = 'WIRE'
    cutter.hide_render = True

# Add Bevel Modifier
if "Bevel_Clean" not in target.modifiers:
    bev = target.modifiers.new(name="Bevel_Clean", type='BEVEL')
    bev.width = 0.015
    bev.segments = 2
    bev.limit_method = 'ANGLE'
    bev.angle_limit = 0.523599 # 30 degrees

# Add Weighted Normal Modifier
if "WeightedNormal" not in target.modifiers:
    wn = target.modifiers.new(name="WeightedNormal", type='WEIGHTED_NORMAL')
    wn.keep_sharp = True
    target.data.use_auto_smooth = True

print(f"Applied non-destructive boolean stack to {target.name}")
```
