"""
Skill Manager for Blender MCP Chat.
Dynamic 2-Tier Hierarchical Router:
1. Detects Domain from prompt intent.
2. Scores and matches top skills within domain and across catalog.
3. Dynamically injects concise, verified recipes into LLM prompt with plugin awareness.
Zero external dependencies.
"""

import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple

try:
    from plugin_manager import plugin_mgr
except ImportError:
    plugin_mgr = None


class SkillManager:
    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.skills_dir = os.path.join(self.base_dir, "skills")
        else:
            self.skills_dir = skills_dir

        self.index_path = os.path.join(self.skills_dir, "index.json")
        self._catalog: Optional[Dict[str, Any]] = None
        self._load_catalog()

    def _load_catalog(self):
        """Loads index.json into memory cache."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self._catalog = json.load(f)
            except Exception:
                self._catalog = {"version": "1.0", "domains": [], "skills": []}
        else:
            self._catalog = {"version": "1.0", "domains": [], "skills": []}

    def reload(self):
        """Reloads catalog from disk."""
        self._load_catalog()

    def get_all_skills(self) -> List[Dict[str, Any]]:
        if not self._catalog:
            return []
        return self._catalog.get("skills", [])

    def detect_domain(self, prompt: str) -> Optional[str]:
        """
        Fast 1st-tier intent classification: maps keywords to one of the 10 domains.
        """
        p_lower = prompt.lower()
        domain_keywords = {
            "pipeline_gamedev": ["언리얼", "유니티", "고도", "ue5", "ue4", "unity", "godot", "lod", "ucx", "소켓", "socket", "export", "fbx", "gltf"],
            "camera_lighting": ["카메라", "턴테이블", "turntable", "조명", "3점", "라이팅", "렌더", "eevee", "cycles", "dof", "피사계 심도", "줌인", "크레인"],
            "rigging": ["리깅", "아마추어", "뼈대", "rig", "rigify", "armature", "bone", "ik", "웨이트 페인트"],
            "animation": ["애니메이션", "모션", "걷기", "루프", "f-curve", "spin", "자전", "회전 애니"],
            "physics": ["물리", "리지드", "rigid", "시뮬레이션", "천 물리", "cloth", "충돌체", "바람"],
            "vfx": ["이펙트", "지오메트리 노드", "geonodes", "파티클", "먼지", "스파크", "연기", "vfx"],
            "materials": ["재질", "머티리얼", "셰이더", "pbr", "ambientcg", "uv", "언랩", "unwrap", "텍스처", "베이킹"],
            "hard_surface": ["하드서페이스", "부품", "메카닉", "불리언", "boolean", "패널", "파이프", "배관", "케이블", "트러스"],
            "character": ["캐릭터", "스컬핑", "sculpt", "리메시", "remesh", "리토폴로지", "인체", "페이스", "얼굴"],
            "environment": ["배경", "지형", "모듈러", "룸", "방 만들기", "건물", "인테리어", "landscape", "terrain"]
        }

        for domain, keywords in domain_keywords.items():
            for kw in keywords:
                if kw in p_lower:
                    return domain
        return None

    def match_skills(self, prompt: str, max_count: int = 2) -> List[Dict[str, Any]]:
        """
        2nd-tier scoring: ranks skills based on trigger keyword matches and domain alignment.
        """
        if not prompt or not self._catalog:
            return []

        p_lower = prompt.lower()
        detected_domain = self.detect_domain(prompt)
        scored_skills: List[Tuple[int, Dict[str, Any]]] = []

        for skill in self.get_all_skills():
            score = 0
            # Domain bonus
            if detected_domain and skill.get("domain") == detected_domain:
                score += 15

            # Trigger matching
            triggers = skill.get("triggers", [])
            for trg in triggers:
                trg_l = trg.lower()
                if trg_l in p_lower:
                    # Longer triggers get more weight
                    score += 10 + len(trg_l)

            if score > 0:
                scored_skills.append((score, skill))

        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_skills[:max_count]]

    def read_skill_content(self, skill_item: Dict[str, Any], compact: bool = True) -> str:
        """
        Reads markdown content for a skill file.
        When compact=True, distills the content to rules and code snippets to prevent context bloat.
        When compact=False, returns the complete raw documentation.
        """
        rel_file = skill_item.get("file", "")
        if not rel_file:
            return ""

        full_path = os.path.join(self.base_dir, rel_file)
        if not os.path.exists(full_path):
            full_path = os.path.join(self.skills_dir, os.path.basename(rel_file))

        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                    # Strip YAML frontmatter if present for token efficiency
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            text = parts[2].strip()

                    if not compact:
                        return text

                    # Compact mode: Distill rules, directives, and verified code blocks
                    lines = text.splitlines()
                    compact_lines = []
                    in_code = False
                    for line in lines:
                        sline = line.strip()
                        if sline.startswith("```"):
                            in_code = not in_code
                            compact_lines.append(line)
                            continue
                        if in_code:
                            compact_lines.append(line)
                            continue
                        # Keep section headers, bullet points, numbered lists, and directives
                        if sline.startswith("#") or sline.startswith("-") or sline.startswith("*"):
                            compact_lines.append(line)
                        elif len(sline) > 2 and sline[0].isdigit() and sline[1] in (".", ")"):
                            compact_lines.append(line)
                        elif sline.startswith("Prime Directive:") or sline.startswith("Summary:"):
                            compact_lines.append(line)

                    result = "\n".join(compact_lines).strip()
                    if len(result) > 40:
                        return result
                    return text[:1200]
            except Exception:
                pass

        # If file not yet on disk, return summary recipe
        return f"## Skill: {skill_item.get('name')}\nSummary: {skill_item.get('summary', '')}"

    def classify_task(self, prompt: str) -> Dict[str, Any]:
        """
        Classifies task complexity into 'simple', 'moderate', or 'complex'.
        Returns structured metadata including domain, matched skills, recommended reasoning effort,
        thinking budget, and max agent iterations.
        """
        if not prompt or not isinstance(prompt, str):
            return {
                "level": "simple",
                "domain": None,
                "matched_skills": [],
                "recommended_effort": "low",
                "recommended_thinking_budget": 0,
                "max_agent_turns": 2,
                "skip_scene_inspection": True,
            }

        p = prompt.strip().lower()

        # Check for complex indicators:
        # Long text, multi-line, multi-step pipeline conjunctions, or heavy domain tasks
        is_long = len(p) > 100 or "\n" in p
        complex_triggers = (
            "plan", "계획", "단계", "step", "리깅", "아마추어", "rig", "bone",
            "ik", "웨이트", "weight", "익스포트", "export", "fbx", "gltf",
            "애니메이션", "animation", "시뮬레이션", "simulation", "물리", "physics",
            "천 물리", "cloth", "베이킹", "baking", "언랩", "unwrap", "retopology",
            "리토폴로지", "모듈러", "modular", "지형", "landscape", "terrain",
            "스컬핑", "sculpt", "인체", "캐릭터", "character", "건물", "building",
            "인테리어", "interior", "하고 난", "한 다음", "한 뒤", "and then", "after that"
        )
        is_complex = is_long or any(k in p for k in complex_triggers)

        # Check for simple indicators
        simple_patterns = (
            "큐브", "정육면체", "cube", "구체", "sphere", "uv sphere", "ico sphere",
            "원통", "실린더", "cylinder", "원뿔", "cone", "평면", "plane", "그리드", "grid",
            "토러스", "torus", "도넛", "수잔", "원숭이", "monkey", "suzanne",
            "엠티", "empty", "카메라 하나", "조명 하나", "light 하나", "점광원", "point light",
            "삭제", "지워", "delete", "remove", "clear", "초기화", "reset",
            "색상", "색깔", "color", "빨간", "파란", "노란", "초록", "검은", "하얀", "흰색",
            "스케일", "크기", "scale", "회전", "rotate", "이동", "move", "숨겨", "hide"
        )
        is_simple = (not is_complex) and len(p) <= 80 and any(k in p for k in simple_patterns)

        domain = self.detect_domain(prompt)

        if is_simple:
            return {
                "level": "simple",
                "domain": domain,
                "matched_skills": [],
                "recommended_effort": "low",
                "recommended_thinking_budget": 0,
                "max_agent_turns": 2,
                "skip_scene_inspection": True,
            }

        matched = self.match_skills(prompt, max_count=2 if is_complex else 1)

        if is_complex:
            return {
                "level": "complex",
                "domain": domain,
                "matched_skills": matched,
                "recommended_effort": "high",
                "recommended_thinking_budget": 2048,
                "max_agent_turns": 6,
                "skip_scene_inspection": False,
            }

        # Moderate
        return {
            "level": "moderate",
            "domain": domain,
            "matched_skills": matched,
            "recommended_effort": "medium",
            "recommended_thinking_budget": 1024,
            "max_agent_turns": 4,
            "skip_scene_inspection": False,
        }

    def build_injection_prompt(self, prompt: str) -> str:
        """
        Synthesizes a compact, dynamic context block with matched skills and plugin strategies.
        Uses task classification to inject only the necessary skills.
        """
        info = self.classify_task(prompt)
        if info["level"] == "simple":
            return ""

        matched = info.get("matched_skills", [])
        if not matched:
            return ""

        parts = ["\n[Referenced Standard Blender Skills & Recipes]"]
        collected_addons = set()

        for skill in matched:
            content = self.read_skill_content(skill, compact=True)
            parts.append(f"\n--- SKILL: {skill.get('name')} ({skill.get('id')}) ---")
            parts.append(content)
            for addon in skill.get("optional_addons", []):
                collected_addons.add(addon)

        # Plugin resolution
        if plugin_mgr and collected_addons:
            addon_strat = plugin_mgr.resolve_addon_instructions(list(collected_addons))
            if addon_strat:
                parts.append(addon_strat)

        parts.append("--- END SKILLS ---\n")
        return "\n".join(parts)

    def tool_lookup(self, query: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Function calling handler when LLM calls lookup_blender_skill.
        """
        matched = self.match_skills(query, max_count=3)
        if not matched and domain:
            matched = [s for s in self.get_all_skills() if s.get("domain") == domain][:2]

        if not matched:
            return {
                "status": "not_found",
                "message": f"No specific Blender skill matched query: '{query}'. Proceed with standard bpy.",
                "available_domains": [d["id"] for d in self._catalog.get("domains", [])]
            }

        results = []
        for s in matched:
            results.append({
                "id": s.get("id"),
                "name": s.get("name"),
                "summary": s.get("summary"),
                "recipe": self.read_skill_content(s, compact=False)
            })

        return {
            "status": "success",
            "count": len(results),
            "skills": results
        }


skill_mgr = SkillManager()
