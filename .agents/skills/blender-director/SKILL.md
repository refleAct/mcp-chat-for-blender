---
name: blender-director
description: Analyzes complex 3D requests and routes automatically to specialized pipeline skills.
domain: pipeline_gamedev
triggers: 디렉터, director, 파이프라인 라우터, blender-director
---

# Blender Director
Decomposes requests into Blockout -> High Poly -> Low Poly -> UV -> PBR -> Export.

## Routing Logic
- Prop / Weapon -> hard-surface -> uv-workflow -> materials -> unreal-export
- Environment -> modular-kit -> props-scattering -> lighting
- Character -> base-mesh -> retopology -> rigging
