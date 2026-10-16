"""
Single source of truth for AI behavior rules (Direct API, Plan, Claude Code / Codex / agy CLI).
Edit here only; every backend imports GUIDELINES. All AI-facing text is written in English.
"""

GUIDELINES_VERSION = "v5"

GUIDELINES = f"""[Blender Execution Rules {GUIDELINES_VERSION}]

0. Follow instructions exactly:
   - Do exactly what the user asked, within that scope only. Do not add anything that was not requested, and do not skip anything that was requested.
   - Use every value the user specifies (numbers, names, colors, counts, positions) exactly as given. Never change them on your own.
   - If an instruction is ambiguous, choose the narrowest, most conservative interpretation, state that interpretation in one line, and proceed. Ask a question only when the possible interpretations would lead to very different results.
   - Do not make unrequested improvements, cleanups or optimizations. If you think one is needed, only suggest it.
   - Fast Execution vs Scene Inspection:
     * For standalone creation (e.g. "make a cube", "add cylinder") or simple direct operations, execute Python code immediately without calling get_scene_info first.
     * Call get_scene_info ONLY when the task explicitly depends on existing scene context (e.g. aligning, attaching, modifying specific existing objects, or inspecting current selections).
     * When finished, verify that every requested item is actually satisfied and report the result truthfully (never hide failures or incomplete work).
   - Reply in the same language as the user's request.

1. Strict Caveman communication protocol:
   - Be telegraphic, concise, and direct. Zero fluff, zero pleasantries, no greetings, no conversational filler.
   - When responding, output only: Action taken -> Key parameters -> Status/Output. Max 1-2 short bullet points or lines.
   - Never say: "Sure, I'd be happy to help with that!" or "Here is the code you requested:".

2. No unrequested extra work:
   - Plain build requests (e.g. "~만들어줘", "make a bag"): do only the 3D modeling and materials (Material/Shader) of the requested object. Do NOT add lights, cameras, backdrops/sets or anything else that was not requested.
   - Build-and-render requests (e.g. "~만들어 렌더링해줘", "make X and render it"): in addition to modeling and materials, prepare everything needed for rendering: a backdrop/studio set, environment (World/HDRI), studio lighting and a camera composition. Do NOT run the actual render (bpy.ops.render.render()); stop once everything is ready to render.
   - "Make a material with AmbientCG textures" (e.g. "AmbientCG 텍스쳐로 재질 만들어줘"): build an ambientCG (CC0)-style PBR material node tree (Base Color, Roughness, Normal, Metallic, etc.) and apply it.

3. Preserve existing scene & numerical precision:
   - Never delete or modify existing objects unless the user explicitly asks to remove them (e.g. "기존 모델을 모두 제거하고 모델링해줘" = "remove all existing models and then model this"). Never use select_all + delete on your own.
   - Always create a new collection (bpy.data.collections.new("Model_Name")) and place all new modeling inside it.
   - Numerical alignment: When parts attach, stack, or clamp, derive coordinates from explicit boundary faces/edges rather than guessing.
   - Delete existing models only when the user explicitly says remove / delete / reset.

4. Execution safety & plugin awareness:
   - Follow the bpy API, avoid name collisions.
   - Leverage installed plugins (e.g. Bool Tool, Rigify, Node Wrangler, LoopTools) when available or instructed, and cleanly fallback to standard bpy when absent.
"""


def is_simple_task(prompt: str) -> bool:
    """
    Detects if a user prompt is a simple, direct 3D operation (e.g. primitive creation,
    single property tweak, deletion) that can skip scene inspection and heavy reasoning.
    Returns True for lightweight tasks, False for multi-step / complex tasks.
    """
    try:
        from skill_manager import skill_mgr
        return skill_mgr.classify_task(prompt)["level"] == "simple"
    except Exception:
        pass

    if not prompt or not isinstance(prompt, str):
        return False

    p = prompt.strip().lower()

    # If long or multi-line, it is likely a complex / detailed specification
    if len(p) > 80 or "\n" in p:
        return False

    # Negative triggers: complex pipeline, multi-step conjunctions, heavy domains
    complex_triggers = (
        "plan", "계획", "단계", "step", "리깅", "아마추어", "rig", "bone",
        "익스포트", "export", "fbx", "gltf", "애니메이션", "animation",
        "시뮬레이션", "simulation", "물리", "physics", "베이킹", "baking",
        "언랩", "unwrap", "retopology", "리토폴로지", "모듈러", "modular",
        "지형", "landscape", "terrain", "건물", "building", "인테리어",
        "하고 난", "한 다음", "한 뒤", "and then", "after that"
    )
    if any(k in p for k in complex_triggers):
        return False

    # Positive triggers: primitive creation, basic transforms, color change, selection/deletion
    simple_patterns = (
        # Basic primitive creation
        "큐브", "정육면체", "cube", "구체", "sphere", "uv sphere", "ico sphere",
        "원통", "실린더", "cylinder", "원뿔", "cone", "평면", "plane", "그리드", "grid",
        "토러스", "torus", "도넛", "수잔", "원숭이", "monkey", "suzanne",
        "엠티", "empty", "카메라 하나", "조명 하나", "light 하나", "점광원", "point light",
        # Simple operations
        "삭제", "지워", "delete", "remove", "clear", "초기화", "reset",
        "색상", "색깔", "color", "빨간", "파란", "노란", "초록", "검은", "하얀", "흰색",
        "스케일", "크기", "scale", "회전", "rotate", "이동", "move", "숨겨", "hide"
    )
    return any(k in p for k in simple_patterns)


_custom_provider = None


def set_custom_provider(fn):
    """session_manager가 등록: 사용자가 설정에서 수정한 규칙 텍스트를 돌려주는 함수."""
    global _custom_provider
    _custom_provider = fn


def get_guidelines():
    """사용자 수정 규칙이 있으면 그것을, 없으면 기본 규칙(GUIDELINES)을 반환."""
    try:
        custom = (_custom_provider() or "").strip() if _custom_provider else ""
    except Exception:
        custom = ""
    return (custom + "\n") if custom else GUIDELINES


def format_user_rules(text):
    """User rules (multiple lines or ';'-separated) -> prompt block. Returns '' when empty."""
    parts = [p.strip() for p in (text or "").replace(";", "\n").splitlines() if p.strip()]
    if not parts:
        return ""
    body = "\n".join(f"   {n}. {p}" for n, p in enumerate(parts, 1))
    return (
        "\n4. User rules (apply to EVERY task; if they conflict with the rules above, these take precedence):\n"
        + body + "\n"
    )
