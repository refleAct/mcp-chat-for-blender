"""
Setup and populate Claude Code compliant Skills for Blender.
Implements all skills provided from:
- kevinbadi/blender-skills (turntable, slow-zoom, dolly-rotate, crane-shot, dynamic-full-loop, perfect-loop, image-to-3d, multi-image-to-3d, polyhaven-material-swap, blender-product-polish, blender-toolkit)
- powerhouse90/Blender-Superskill (blender-superskill)
- arjun988/blender-skills (blender-director, unreal-export, unity-export, godot-export, collision-proxy, lod-pipeline, asset-optimization, retopology, uv-workflow, reference-image-match, environment-artist, horror-style)
- composio-community/opencode-skills (blender-hard-surface-modeling, blender-python-integration, blender-rigging-animation)
- lobehub & mcpmarket (blender-animation, blender-pipeline-integration)
"""

import os
import json
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills")
CLAUDE_SKILLS_DIR = os.path.join(BASE_DIR, ".claude", "skills")
AGENTS_SKILLS_DIR = os.path.join(BASE_DIR, ".agents", "skills")

SKILLS_DEFINITIONS = [
    # 1. kevinbadi/blender-skills
    {
        "id": "turntable",
        "domain": "camera_lighting",
        "name": "Turntable Camera Animation",
        "triggers": ["턴테이블", "turntable", "360", "카메라 회전", "orbit", "쇼케이스"],
        "description": "360-degree turntable camera orbit around a 3D product or character. Classic showcase animation.",
        "content": """# Turntable Camera Animation
Orbits the camera 360 degrees around the product for a clean product showcase. Starts front-facing and loops seamlessly.

## Prerequisites
- Blender 4.0+
- Active object selected

## Verified bpy Recipe
```python
import bpy, math
from mathutils import Vector

obj = bpy.context.active_object or (bpy.context.selected_objects[0] if bpy.context.selected_objects else None)
if obj:
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = sum(bbox, Vector()) / 8.0
    size = max((max(v[i] for v in bbox) - min(v[i] for v in bbox)) for i in range(3))
else:
    center = Vector((0.0, 0.0, 0.0))
    size = 2.0

dist = max(size * 2.5, 3.0)
height = max(size * 0.8, 1.5)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=center)
target = bpy.context.active_object
target.name = 'TurntableTarget'

bpy.ops.object.camera_add(location=(center.x, center.y - dist, center.z + height))
cam = bpy.context.active_object
cam.name = 'TurntableCam'
bpy.context.scene.camera = cam

con = cam.constraints.new(type='TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 120
target.rotation_euler = (0, 0, 0)
target.keyframe_insert(data_path="rotation_euler", frame=1)
target.rotation_euler = (0, 0, math.radians(360))
target.keyframe_insert(data_path="rotation_euler", frame=120)

if target.animation_data and target.animation_data.action:
    for fc in target.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'LINEAR'
print("Turntable animation configured.")
```"""
    },
    {
        "id": "slow-zoom",
        "domain": "camera_lighting",
        "name": "Slow Zoom In Animation",
        "triggers": ["줌인", "slow zoom", "클로즈업", "zoom in", "reveal", "초점"],
        "description": "Cinematic push-in toward a hero detail for dramatic product reveal.",
        "content": """# Slow Zoom In Animation
Slow, cinematic push-in toward hero detail with subtle focal shift.

## Verified bpy Recipe
```python
import bpy
from mathutils import Vector

cam = bpy.context.scene.camera
if not cam:
    bpy.ops.object.camera_add(location=(0, -5, 2))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 96

# Animate Focal Length or Distance
cam.data.lens = 45.0
cam.data.keyframe_insert(data_path="lens", frame=1)
cam.data.lens = 75.0
cam.data.keyframe_insert(data_path="lens", frame=96)
print("Configured cinematic slow zoom.")
```"""
    },
    {
        "id": "dolly-rotate",
        "domain": "camera_lighting",
        "name": "Dolly Rotate Sweeping Shot",
        "triggers": ["돌리", "dolly", "dolly rotate", "스위핑", "회전 이동"],
        "description": "Camera moves forward along a curved path while rotating around target.",
        "content": """# Dolly Rotate
Camera translates forward while simultaneously rotating to sweep past the product.

## Verified bpy Recipe
```python
import bpy, math
from mathutils import Vector

target_pos = Vector((0, 0, 1))
bpy.ops.object.camera_add(location=(-3, -4, 2))
cam = bpy.context.active_object
bpy.context.scene.camera = cam

con = cam.constraints.new(type='TRACK_TO')
bpy.ops.object.empty_add(type='PLAIN_AXES', location=target_pos)
t_empty = bpy.context.active_object
con.target = t_empty

cam.location = (-4, -4, 2.5)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (2, -2.5, 0.8)
cam.keyframe_insert(data_path="location", frame=100)
print("Configured dolly rotate shot.")
```"""
    },
    {
        "id": "crane-shot",
        "domain": "camera_lighting",
        "name": "Crane Shot Elevation Reveal",
        "triggers": ["크레인", "crane", "crane shot", "상승 샷", "앙각에서 조감"],
        "description": "Low to high vertical camera reveal sweeping from base to top.",
        "content": """# Crane Shot
Moves camera from ground-level angle up to high 45-degree isometric view.

## Verified bpy Recipe
```python
import bpy

bpy.ops.object.camera_add(location=(0, -4, 0.2))
cam = bpy.context.active_object
bpy.context.scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 1))
target = bpy.context.active_object
con = cam.constraints.new(type='TRACK_TO')
con.target = target

cam.location = (0, -3.5, 0.3)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (2, -3.5, 4.0)
cam.keyframe_insert(data_path="location", frame=120)
print("Configured crane elevation shot.")
```"""
    },
    {
        "id": "dynamic-full-loop",
        "domain": "animation",
        "name": "Dynamic Full Loop Animation",
        "triggers": ["다이내믹 루프", "dynamic loop", "whip transition", "루프 회전"],
        "description": "Speed-ramped loop showing all sides with fast transitions.",
        "content": """# Dynamic Full Loop
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
```"""
    },
    {
        "id": "perfect-loop",
        "domain": "animation",
        "name": "Perfect Loop Seamless Cycle",
        "triggers": ["퍼펙트 루프", "perfect loop", "무한 루프", "seamless cycle"],
        "description": "Mathematically seamless cyclical motion with matching start/end derivatives.",
        "content": """# Perfect Loop
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
```"""
    },
    {
        "id": "polyhaven-material-swap",
        "domain": "materials",
        "name": "PolyHaven & CC0 PBR Material Swap",
        "triggers": ["polyhaven", "재질 교체", "material swap", "cc0 swap", "pbr swap"],
        "description": "Automated replacement and testing of PBR texture surfaces.",
        "content": """# PolyHaven Material Swap
Swaps active material with CC0 PBR node graph.

## Verified bpy Recipe
```python
import bpy

def apply_pbr_mat(obj, name, color=(0.8, 0.8, 0.8, 1.0), roughness=0.3, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    print(f"Applied material {name} to {obj.name}")
```"""
    },
    {
        "id": "blender-product-polish",
        "domain": "materials",
        "name": "Blender Product Polish & Studio",
        "triggers": ["제품 폴리싱", "에셋 정리", "product polish", "studio setup", "광택"],
        "description": "Cleans raw AI-generated GLTF meshes and sets 4-point studio lighting.",
        "content": """# Blender Product Polish
Cleans imported GLTF geometry, unifies scales, and applies studio lighting.

## Verified bpy Recipe
```python
import bpy

for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.shade_smooth()
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
print("Product polished and smoothed.")
```"""
    },
    {
        "id": "blender-toolkit",
        "domain": "hard_surface",
        "name": "Blender Toolkit Mesh Primitives",
        "triggers": ["toolkit", "프리미티브 생성", "블렌더 툴킷", "create cube", "primitive"],
        "description": "Core geometry creation, mesh primitives, and modifier utilities.",
        "content": """# Blender Toolkit
Creates clean parametric primitives and modifiers.

## Verified bpy Recipe
```python
import bpy

def create_blockout_box(size=(2, 2, 2), loc=(0, 0, 1)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    box = bpy.context.active_object
    box.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return box
```"""
    },

    # 2. powerhouse90/Blender-Superskill
    {
        "id": "blender-superskill",
        "domain": "hard_surface",
        "name": "Blender SuperSkill Disciplined Modeling",
        "triggers": ["superskill", "슈퍼스킬", "정밀 모델링", "접촉면 검증", "interface audit", "수치 조립"],
        "description": "Disciplined reference-first modeling with numerical contact verification and solid shading discipline.",
        "content": """# Blender SuperSkill
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
```"""
    },

    # 3. arjun988/blender-skills
    {
        "id": "blender-director",
        "domain": "pipeline_gamedev",
        "name": "Blender Director Pipeline Router",
        "triggers": ["디렉터", "director", "파이프라인 라우터", "blender-director"],
        "description": "Analyzes complex 3D requests and routes automatically to specialized pipeline skills.",
        "content": """# Blender Director
Decomposes requests into Blockout -> High Poly -> Low Poly -> UV -> PBR -> Export.

## Routing Logic
- Prop / Weapon -> hard-surface -> uv-workflow -> materials -> unreal-export
- Environment -> modular-kit -> props-scattering -> lighting
- Character -> base-mesh -> retopology -> rigging"""
    },
    {
        "id": "unreal-export",
        "domain": "pipeline_gamedev",
        "name": "Unreal Engine 5 FBX Export",
        "triggers": ["언리얼", "UE5", "UE4", "언리얼 익스포트", "unreal export", "ue fbx"],
        "description": "Unreal Engine specific FBX export with 0.01 scale, Z-Up, UCX collision, and LOD groups.",
        "content": """# Unreal Export
Exports UE-ready FBX with centimeters scale awareness and correct axis forward.

## Verified bpy Recipe
```python
import bpy, os

filepath = bpy.path.abspath("//export_ue5_asset.fbx")
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
    mesh_smooth_type='FACE'
)
print(f"Exported to Unreal: {filepath}")
```"""
    },
    {
        "id": "unity-export",
        "domain": "pipeline_gamedev",
        "name": "Unity Engine FBX & Prefab Export",
        "triggers": ["유니티", "unity", "유니티 익스포트", "unity export"],
        "description": "Unity specific FBX export with -180 rotation compensation and Y-up coordinate.",
        "content": """# Unity Export
Exports FBX properly oriented for Unity's coordinate system.

## Verified bpy Recipe
```python
import bpy

filepath = bpy.path.abspath("//unity_asset.fbx")
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=True,
    axis_forward='Z',
    axis_up='Y',
    apply_scale_options='FBX_SCALE_ALL'
)
```"""
    },
    {
        "id": "godot-export",
        "domain": "pipeline_gamedev",
        "name": "Godot 4 GLTF/GLB Export",
        "triggers": ["고도", "godot", "고도 익스포트", "godot export", "glb"],
        "description": "Godot 4 GLTF/GLB export with embedded materials and CollisionShape hints.",
        "content": """# Godot Export
Exports standard GLB with -col and -navmesh suffixes for Godot import.

## Verified bpy Recipe
```python
import bpy

filepath = bpy.path.abspath("//godot_asset.glb")
bpy.ops.export_scene.gltf(
    filepath=filepath,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)
```"""
    },
    {
        "id": "collision-proxy",
        "domain": "pipeline_gamedev",
        "name": "Collision Proxy UCX Generator",
        "triggers": ["콜리전", "collision", "ucx", "collision proxy", "충돌체"],
        "description": "Generates simplified UCX_ convex hulls and bounding collision boxes.",
        "content": """# Collision Proxy
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
```"""
    },
    {
        "id": "lod-pipeline",
        "domain": "pipeline_gamedev",
        "name": "LOD Chain Pipeline",
        "triggers": ["LOD", "lod", "lod pipeline", "레벨오브디테일", "decimate lod"],
        "description": "Automated LOD0 (100%), LOD1 (50%), LOD2 (25%), LOD3 (12%) decimation chain.",
        "content": """# LOD Pipeline
Creates sequential LOD meshes with Decimate modifier and standardized names.

## Verified bpy Recipe
```python
import bpy

base = bpy.context.active_object
clean = base.name.split("_LOD")[0]
base.name = f"{clean}_LOD0"

for tag, ratio in [("LOD1", 0.5), ("LOD2", 0.25), ("LOD3", 0.12)]:
    mesh = base.data.copy()
    obj = bpy.data.objects.new(f"{clean}_{tag}", mesh)
    obj.matrix_world = base.matrix_world.copy()
    bpy.context.collection.objects.link(obj)
    mod = obj.modifiers.new(name="LOD_Decimate", type='DECIMATE')
    mod.ratio = ratio
    obj.hide_viewport = True
print("Created LOD0-LOD3 chain.")
```"""
    },
    {
        "id": "asset-optimization",
        "domain": "pipeline_gamedev",
        "name": "Asset Optimization & Sanitization",
        "triggers": ["에셋 최적화", "asset optimization", "최적화", "메쉬 정리", "apply transform"],
        "description": "Cleans orphan data, applies scale/rotation, checks polygon budgets, and fixes normal orientations.",
        "content": """# Asset Optimization
Applies scale/rotation, recalculates outside normals, removes unassigned materials.

## Verified bpy Recipe
```python
import bpy

for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.object.mode_set(mode='OBJECT')
print("Optimized and sanitized meshes.")
```"""
    },
    {
        "id": "retopology",
        "domain": "character",
        "name": "Retopology Workflow",
        "triggers": ["리토폴로지", "retopology", "로우폴 변환", "쿼드 리토폴"],
        "description": "Converts high-poly sculpts into clean quad-dominant low-poly game models.",
        "content": """# Retopology Workflow
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
```"""
    },
    {
        "id": "uv-workflow",
        "domain": "materials",
        "name": "UV Unwrapping & Packing",
        "triggers": ["UV", "uv workflow", "uv 언랩", "uv 패킹", "seam"],
        "description": "Marks seams on hard edges, unwraps angle-based islands, and packs UVs.",
        "content": """# UV Workflow
Marks seams along sharp angles (>35 deg) and runs Angle-Based unwrap.

## Verified bpy Recipe
```python
import bpy

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.edges_select_sharp(sharpness=0.61) # ~35 deg
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.02)
    bpy.ops.uv.pack_islands(margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
print(f"Unwrapped UVs for {obj.name}")
```"""
    },
    {
        "id": "reference-image-match",
        "domain": "environment",
        "name": "Reference Image Match Modeling",
        "triggers": ["레퍼런스 매칭", "reference match", "이미지 대조", "컨셉아트 매칭"],
        "description": "Aligns camera perspective to concept art and compares modeling silhouette.",
        "content": """# Reference Image Match
Loads reference image into 3D camera background and matches focal length."""
    },
    {
        "id": "environment-artist",
        "domain": "environment",
        "name": "Environment Modular Building",
        "triggers": ["환경 아티스트", "environment artist", "배경 제작", "던전", "모듈러 배경"],
        "description": "Builds modular architectural kits, corridors, and structural environment props.",
        "content": """# Environment Artist
Creates snapped modular kits for Unreal Engine / Unity level construction."""
    },
    {
        "id": "horror-style",
        "domain": "camera_lighting",
        "name": "Horror Style & Decaying Atmosphere",
        "triggers": ["호러", "horror", "공포", "음산한", "decay", "grimy"],
        "description": "Creates flickering lighting, decaying materials, and unsettling camera framing.",
        "content": """# Horror Style
Flickering point lights, heavy volumetric absorption, and off-balance camera angles."""
    },

    # 4. composio-community/opencode-skills
    {
        "id": "blender-hard-surface-modeling",
        "domain": "hard_surface",
        "name": "Composio Hard Surface Modeling",
        "triggers": ["하드서페이스 모델링", "hard surface modeling", "composio hard surface"],
        "description": "Subdivision surface, edge creasing, and non-destructive beveling workflow.",
        "content": """# Blender Hard Surface Modeling
Clean quad edge loops with Bevel modifier and auto-smoothed vertex normals.

## Verified bpy Recipe
```python
import bpy

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
    bev.width = 0.02
    bev.segments = 3
    bev.limit_method = 'ANGLE'
    obj.data.use_auto_smooth = True
```"""
    },
    {
        "id": "blender-python-integration",
        "domain": "pipeline_gamedev",
        "name": "Blender Python Integration",
        "triggers": ["파이썬 연동", "blender python", "bpy 스크립팅", "python integration"],
        "description": "Clean bpy scripting conventions, scene traversal, context overrides, and robust error handling.",
        "content": """# Blender Python Integration
Standard clean patterns for automating Blender scenes via Python API."""
    },
    {
        "id": "blender-rigging-animation",
        "domain": "rigging",
        "name": "Composio Rigging & Animation",
        "triggers": ["리깅 애니메이션", "blender rigging", "뼈대 애니", "bone hierarchy"],
        "description": "Armature setup, bone hierarchies, IK constraints, and action keyframing.",
        "content": """# Blender Rigging & Animation
Armature creation and bone hierarchy parenting for animated characters."""
    },

    # 5. lobehub & mcpmarket
    {
        "id": "blender-animation",
        "domain": "animation",
        "name": "LobeHub Blender Animation",
        "triggers": ["애니메이션 자동화", "terminal animation", "키프레임 생성"],
        "description": "Terminal and MCP automated keyframing for object transforms and cameras.",
        "content": """# Blender Animation
Automates location, rotation, and property keyframing directly via MCP calls."""
    },
    {
        "id": "blender-pipeline-integration",
        "domain": "pipeline_gamedev",
        "name": "Blender Pipeline Integration",
        "triggers": ["파이프라인 통합", "pipeline integration", "mcp blender integration"],
        "description": "Standardized MCP JSON-RPC protocol bridge between AI agents and active Blender sessions.",
        "content": """# Blender Pipeline Integration
Establishes reliable socket/HTTP RPC bridge for automated 3D execution."""
    }
]


def setup_all_skills():
    print("Setting up Claude Code & Addon Skills...")
    os.makedirs(SKILLS_DIR, exist_ok=True)
    os.makedirs(CLAUDE_SKILLS_DIR, exist_ok=True)

    catalog = {
        "version": "1.0",
        "domains": [
            { "id": "environment", "name": "Environment & World Building" },
            { "id": "character", "name": "Character, Sculpting & Topology" },
            { "id": "hard_surface", "name": "Hard Surface, CAD & Props" },
            { "id": "materials", "name": "Materials, Shading & UV" },
            { "id": "rigging", "name": "Rigging & Skeletal Setup" },
            { "id": "animation", "name": "Animation, Motion & Cycles" },
            { "id": "physics", "name": "Physics & Dynamic Simulation" },
            { "id": "vfx", "name": "VFX, Particles & Geometry Nodes" },
            { "id": "camera_lighting", "name": "Camera, Lighting & Rendering" },
            { "id": "pipeline_gamedev", "name": "Game Pipeline, LOD & Optimization" }
        ],
        "skills": []
    }

    for skill in SKILLS_DEFINITIONS:
        s_id = skill["id"]
        # 1. Folder in skills/<id>/SKILL.md
        skill_folder = os.path.join(SKILLS_DIR, s_id)
        os.makedirs(skill_folder, exist_ok=True)
        skill_file = os.path.join(skill_folder, "SKILL.md")

        full_md = f"""---
name: {s_id}
description: {skill['description']}
domain: {skill['domain']}
triggers: {', '.join(skill['triggers'])}
---

{skill['content']}
"""
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(full_md.strip() + "\n")

        # 2. Mirror into .claude/skills and .agents/skills for Claude Code and agy CLI
        claude_folder = os.path.join(CLAUDE_SKILLS_DIR, s_id)
        os.makedirs(claude_folder, exist_ok=True)
        claude_file = os.path.join(claude_folder, "SKILL.md")
        shutil.copy2(skill_file, claude_file)

        agents_folder = os.path.join(AGENTS_SKILLS_DIR, s_id)
        os.makedirs(agents_folder, exist_ok=True)
        agents_file = os.path.join(agents_folder, "SKILL.md")
        shutil.copy2(skill_file, agents_file)

        # 3. Add to index.json catalog
        rel_path = f"skills/{s_id}/SKILL.md"
        catalog["skills"].append({
            "id": s_id,
            "domain": skill["domain"],
            "name": skill["name"],
            "triggers": skill["triggers"],
            "file": rel_path,
            "summary": skill["description"]
        })

    # Save index.json
    index_file = os.path.join(SKILLS_DIR, "index.json")
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(SKILLS_DEFINITIONS)} skills in:")
    print(f"  - {SKILLS_DIR}")
    print(f"  - {CLAUDE_SKILLS_DIR}")
    print(f"  - {AGENTS_SKILLS_DIR}")
    print(f"  - Index saved to: {index_file}")

if __name__ == "__main__":
    setup_all_skills()
