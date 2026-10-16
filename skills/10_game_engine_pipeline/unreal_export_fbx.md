---
name: pipe-unreal-engine-fbx
description: Unreal Engine 5 export with 0.01 scale, Z-Up, -Y Forward, and UCX collision awareness.
---

### Standard UE5 Requirements:
- Unreal Engine uses Centimeters (1 Unit = 1 cm).
- Apply all transforms (Ctrl+A -> Location, Rotation, Scale) before export.
- Pivots should be at ground center (0, 0, 0) or character root.
- Collision meshes must be named `UCX_<MeshName>_01`.

### Verified bpy Recipe:
```python
import bpy, os

# 1. Apply Transforms to selected objects
bpy.ops.object.select_all(action='DESELECT')
target_objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in target_objs:
    o.select_set(True)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

# 2. Determine Export Path
out_dir = bpy.path.abspath("//export_ue5")
os.makedirs(out_dir, exist_ok=True)
filepath = os.path.join(out_dir, "Asset_UE5_Export.fbx")

# 3. Export FBX with Unreal Engine standards
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=True,
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',
    axis_up='Y',
    bake_space_transform=True,
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    mesh_smooth_type='FACE',
    add_leaf_bones=False,
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    use_armature_deform_only=True
)
print(f"Exported to Unreal Engine FBX: {filepath}")
```
