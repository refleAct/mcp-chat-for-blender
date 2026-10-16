---
name: collision-proxy
description: Generates simplified UCX_ convex hulls and bounding collision boxes.
domain: pipeline_gamedev
triggers: 콜리전, collision, ucx, collision proxy, 충돌체
---

# Collision Proxy
Creates convex hull mesh prefixed with UCX_<Name>_01 for engine collision.

## Verified bpy Recipe
```python
import bpy, bmesh

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    col_name = f"UCX_{obj.name}_01"
    col_mesh = obj.data.copy()
    col_obj = bpy.data.objects.new(col_name, col_mesh)
    col_obj.matrix_world = obj.matrix_world.copy()
    bpy.context.collection.objects.link(col_obj)
    
    bm = bmesh.new()
    bm.from_mesh(col_mesh)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bm.to_mesh(col_mesh)
    bm.free()
    col_obj.display_type = 'WIRE'
    print(f"Created collision proxy {col_name}")
```
