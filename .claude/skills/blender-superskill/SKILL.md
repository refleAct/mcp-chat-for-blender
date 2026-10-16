---
name: blender-superskill
description: Disciplined reference-first modeling with numerical contact verification and solid shading discipline.
domain: hard_surface
triggers: superskill, 슈퍼스킬, 정밀 모델링, 접촉면 검증, interface audit, 수치 조립
---

# Blender SuperSkill
Prime Directive: If any part is supposed to touch, seat, clamp, bridge, or align to another part, define the exact contact faces/edges/planes first and verify them numerically after the build.

## Rules
1. Inspect reference and derive dimensions from bounding boxes.
2. Derivations over eyeballing.
3. Keep single-user duplicates; always Apply Transforms.
4. Clean planar faces over decorative uninspected bevels.

## Verified bpy Recipe
```python
import bpy
from mathutils import Vector

def align_and_contact(part_a, part_b, offset_z=0.0):
    bbox_a = [part_a.matrix_world @ Vector(c) for c in part_a.bound_box]
    bbox_b = [part_b.matrix_world @ Vector(c) for c in part_b.bound_box]
    top_b = max(v.z for v in bbox_b)
    bottom_a = min(v.z for v in bbox_a)
    shift_z = (top_b - bottom_a) + offset_z
    part_a.location.z += shift_z
    print(f"Aligned {part_a.name} bottom to {part_b.name} top (shift_z={shift_z:.4f})")
```
