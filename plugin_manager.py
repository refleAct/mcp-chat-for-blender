"""
Plugin & Addon Manager for Blender MCP Chat.
Handles real-time addon introspection, safe on-the-fly activation of built-in addons,
and graceful degradation/fallback strategies for third-party plugins.
Zero external dependencies.
"""

import sys
from typing import Dict, Any, List, Tuple, Optional

try:
    import bpy
    import addon_utils
    IN_BLENDER = True
except ImportError:
    bpy = None
    addon_utils = None
    IN_BLENDER = False


# Known built-in and industry standard plugins
KNOWN_PLUGINS = {
    # Built-in Addons (Safe to auto-enable)
    "node_wrangler": {
        "module": "node_wrangler",
        "name": "Node Wrangler",
        "builtin": True,
        "description": "Fast shader node setups, batch texture connect, and node viewers.",
        "fallback": "Standard bpy.data.materials and node_tree.nodes/links manual connection."
    },
    "object_boolean_tools": {
        "module": "object_boolean_tools",
        "name": "Bool Tool",
        "builtin": True,
        "description": "Instant non-destructive difference, union, and slice operations.",
        "fallback": "bpy.ops.object.modifier_add(type='BOOLEAN') with object assignment."
    },
    "mesh_looptools": {
        "module": "mesh_looptools",
        "name": "LoopTools",
        "builtin": True,
        "description": "Circle, bridge, curve, flatten, and space vertex operations.",
        "fallback": "Direct vertex coordinate calculations or subdivide/smooth modifiers."
    },
    "rigify": {
        "module": "rigify",
        "name": "Rigify",
        "builtin": True,
        "description": "Modular procedural rigging system for humanoids and quadrupeds.",
        "fallback": "Single armature with basic bone hierarchy and IK constraints."
    },
    "ant_landscape": {
        "module": "ant_landscape",
        "name": "A.N.T. Landscape",
        "builtin": True,
        "description": "Procedural terrain, mountains, and erosions.",
        "fallback": "Grid plane with Displace modifier and procedural Clouds/Noise texture."
    },
    "add_curve_sapling": {
        "module": "add_curve_sapling",
        "name": "Sapling Tree Gen",
        "builtin": True,
        "description": "Procedural tree, branch, and foliage generation.",
        "fallback": "Trunk extrusion from cylinder with skin modifier or GeoNodes."
    },
    "mesh_f2": {
        "module": "mesh_f2",
        "name": "F2",
        "builtin": True,
        "description": "Fast quad creation from single vertex or edge.",
        "fallback": "Standard bmesh face creation operators."
    },
    "add_mesh_extra_objects": {
        "module": "add_mesh_extra_objects",
        "name": "Extra Objects",
        "builtin": True,
        "description": "Gears, diamonds, pipes, torus variants.",
        "fallback": "Composed primitives with boolean operations."
    },
    # Third-Party Addons (Check existence; fallback if absent)
    "hardops": {
        "module": "hardops",
        "name": "Hard Ops (HOps)",
        "builtin": False,
        "description": "Advanced hard surface boolean, bevel, and sharpen toolset.",
        "fallback": "Bevel Modifier + Weighted Normal Modifier + Auto Smooth (or Shade Auto Smooth in 4.x)."
    },
    "boxcutter": {
        "module": "boxcutter",
        "name": "BoxCutter",
        "builtin": False,
        "description": "Real-time boolean cut workflows.",
        "fallback": "Primitive subtraction using standard Boolean modifier."
    },
    "auto_rig_pro": {
        "module": "auto_rig_pro",
        "name": "Auto-Rig Pro",
        "builtin": False,
        "description": "Complete rigging and game export pipeline with UE/Unity skeleton.",
        "fallback": "Rigify or standard game-ready humanoid armature with root bone."
    }
}


class PluginManager:
    def __init__(self):
        self._cached_addons: Optional[Dict[str, Dict[str, Any]]] = None

    def refresh(self):
        """Invalidate cache."""
        self._cached_addons = None

    def resolve_real_module_name(self, module_name: str) -> Optional[str]:
        """
        Resolves module name, taking into account Blender 4.2+ / 5.x extensions
        (e.g., 'bl_ext.user_default.auto_rig_pro' for 'auto_rig_pro').
        """
        if not IN_BLENDER or addon_utils is None:
            return None
        try:
            for mod in list(addon_utils.modules()):
                mname = getattr(mod, "__name__", "")
                if mname == module_name or mname.endswith(f".{module_name}"):
                    return mname
        except Exception:
            pass
        return None

    def is_addon_installed(self, module_name: str) -> bool:
        """Checks if addon is present in Blender's addon search paths."""
        return self.resolve_real_module_name(module_name) is not None

    def is_addon_enabled(self, module_name: str) -> bool:
        """Checks if addon is currently active."""
        if not IN_BLENDER or addon_utils is None:
            return False
        real_mod = self.resolve_real_module_name(module_name)
        if not real_mod:
            return False
        try:
            loaded, enabled = addon_utils.check(real_mod)
            return bool(enabled)
        except Exception:
            return False

    def ensure_addon(self, module_name: str) -> Tuple[bool, str]:
        """
        Ensures addon is enabled. If built-in and disabled, enables it on-the-fly.
        Returns: (success: bool, message: str)
        """
        if not IN_BLENDER:
            return False, "Not running inside Blender environment."

        real_mod = self.resolve_real_module_name(module_name)
        if not real_mod:
            return False, f"Addon '{module_name}' is not installed in Blender."

        if self.is_addon_enabled(real_mod):
            return True, f"Addon '{real_mod}' is already enabled."

        # Attempt to enable
        try:
            bpy.ops.preferences.addon_enable(module=real_mod)
            if self.is_addon_enabled(real_mod):
                return True, f"Addon '{real_mod}' successfully enabled."
            return False, f"Failed to activate addon '{real_mod}'."
        except Exception as e:
            return False, f"Error enabling addon '{real_mod}': {str(e)}"

    def get_addon_status(self, module_name: str) -> Dict[str, Any]:
        """Returns comprehensive status for given module."""
        info = KNOWN_PLUGINS.get(module_name, {
            "module": module_name,
            "name": module_name,
            "builtin": False,
            "description": "Custom addon",
            "fallback": "Standard bpy implementation."
        })
        installed = self.is_addon_installed(module_name)
        enabled = self.is_addon_enabled(module_name) if installed else False
        return {
            "module": module_name,
            "name": info["name"],
            "installed": installed,
            "enabled": enabled,
            "builtin": info.get("builtin", False),
            "description": info.get("description", ""),
            "fallback": info.get("fallback", "")
        }

    def list_installed_known_addons(self) -> List[Dict[str, Any]]:
        """List status of all known standard addons."""
        return [self.get_addon_status(mod) for mod in KNOWN_PLUGINS]

    def resolve_addon_instructions(self, optional_addons: List[str]) -> str:
        """
        Builds a compact prompt block instructing the LLM whether to use addon operators or fallback.
        """
        if not optional_addons:
            return ""

        instructions = []
        for mod in optional_addons:
            status = self.get_addon_status(mod)
            # Try auto-enabling if built-in
            if status["builtin"] and status["installed"] and not status["enabled"]:
                ok, _ = self.ensure_addon(mod)
                if ok:
                    status["enabled"] = True

            if status["enabled"]:
                instructions.append(
                    f"   - Addon '{status['name']}' is ACTIVE. Use its specialized operators if appropriate."
                )
            else:
                instructions.append(
                    f"   - Addon '{status['name']}' is UNAVAILABLE. FALLBACK to: {status['fallback']}"
                )

        if not instructions:
            return ""

        return "\n[Plugin/Addon Execution Strategy]\n" + "\n".join(instructions) + "\n"


plugin_mgr = PluginManager()
