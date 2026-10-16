---
name: mat-pbr-principled-setup
description: Blender 4.x compatible Principled BSDF node setup with PBR textures or procedural fallbacks.
---

### Standard Workflow:
- In Blender 4.x, Principled BSDF socket names:
  - Base Color
  - Metallic
  - Roughness
  - IOR
  - Alpha
  - Normal
- Auto-set Color Space: sRGB for Base Color; Non-Color for Normal, Roughness, Metallic.

### Verified bpy Recipe:
```python
import bpy

obj = bpy.context.active_object
if not obj or obj.type != 'MESH':
    raise RuntimeError("Select a valid mesh object.")

mat = bpy.data.materials.new(name="PBR_Material")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

# Core Nodes
out_node = nodes.new('ShaderNodeOutputMaterial')
out_node.location = (400, 0)

bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Roughness'].default_value = 0.4
bsdf.inputs['Metallic'].default_value = 0.0
links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

# Texture Coordinate & Mapping
coord = nodes.new('ShaderNodeTexCoord')
coord.location = (-800, 0)
mapping = nodes.new('ShaderNodeMapping')
mapping.location = (-600, 0)
links.new(coord.outputs['UV'], mapping.inputs['Vector'])

# Assign Material to Object
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

print(f"Assigned Blender 4.x PBR shader to {obj.name}")
```
