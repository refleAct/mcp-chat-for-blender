---
name: procedural-texture-generator
description: Generates procedural PBR shader textures using noise, voronoi, bump, and color ramps without external image files.
domain: materials
triggers: 절차적 텍스처, 노드 텍스처, procedural texture, texture maker, procedural shader, 노이즈 셰이더, procedural material
---

# Procedural Texture Generator
Builds infinite, resolution-independent procedural PBR materials using Blender's native shader node graph.

## Verified bpy Recipe
```python
import bpy

def create_procedural_material(obj, mat_name="Procedural_PBR", style="worn_metal"):
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 8.0
    noise.inputs["Detail"].default_value = 6.0
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])

    ramp_col = nodes.new("ShaderNodeValToRGB")
    ramp_col.color_ramp.elements[0].color = (0.15, 0.16, 0.18, 1.0)
    ramp_col.color_ramp.elements[1].color = (0.45, 0.48, 0.52, 1.0)
    links.new(noise.outputs["Fac"], ramp_col.inputs["Fac"])
    links.new(ramp_col.outputs["Color"], bsdf.inputs["Base Color"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = 0.85

    if obj and hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    return mat
```
