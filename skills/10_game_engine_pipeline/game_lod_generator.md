---
name: pipe-game-lod-generator
description: Generate sequential LOD1 (50%), LOD2 (25%), LOD3 (12%) meshes with proper hierarchy naming.
---

### Standard Workflow:
- LOD0: Original base mesh.
- LOD1: Decimate 0.50 (50% tri count).
- LOD2: Decimate 0.25 (25% tri count).
- LOD3: Decimate 0.12 (12% tri count).
- Hierarchy naming: `<Mesh>_LOD0`, `<Mesh>_LOD1`, `<Mesh>_LOD2`, `<Mesh>_LOD3`.

### Verified bpy Recipe:
```python
import bpy

base_obj = bpy.context.active_object
if not base_obj or base_obj.type != 'MESH':
    raise RuntimeError("Select a valid mesh object to generate LODs.")

clean_name = base_obj.name.split("_LOD")[0]
base_obj.name = f"{clean_name}_LOD0"

lod_ratios = [("LOD1", 0.50), ("LOD2", 0.25), ("LOD3", 0.12)]
created_lods = [base_obj.name]

for suffix, ratio in lod_ratios:
    # Duplicate mesh data
    new_mesh = base_obj.data.copy()
    new_mesh.name = f"{clean_name}_{suffix}_Mesh"
    new_obj = bpy.data.objects.new(f"{clean_name}_{suffix}", new_mesh)
    new_obj.matrix_world = base_obj.matrix_world.copy()
    bpy.context.collection.objects.link(new_obj)
    
    # Apply Decimate modifier
    mod = new_obj.modifiers.new(name="Decimate_LOD", type='DECIMATE')
    mod.ratio = ratio
    
    # Hide LODs in viewport except LOD0 to avoid overlap
    new_obj.hide_viewport = True
    created_lods.append(new_obj.name)

print(f"Generated LOD chain: {', '.join(created_lods)}")
```
