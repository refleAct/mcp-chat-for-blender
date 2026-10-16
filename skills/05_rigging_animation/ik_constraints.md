---
name: rig-ik-constraint-setup
description: Configure 2-bone Inverse Kinematics on limbs with knee/elbow pole targets and angle limits.
---

### Standard Workflow:
1. Target Armature must have an IK Control bone (e.g. `Foot_IK.L`) and a Pole Target bone (e.g. `Knee_Pole.L`).
2. Add `IK` constraint on the lower limb bone (e.g. `Shin.L`).
3. Set `chain_count = 2` (affects Thigh and Shin).
4. Assign Target to Armature, Subtarget to `Foot_IK.L`.
5. Assign Pole Target with proper `pole_angle` (typically 90° or -90° depending on bone roll).

### Verified bpy Recipe:
```python
import bpy

arm_obj = bpy.context.active_object
if not arm_obj or arm_obj.type != 'ARMATURE':
    raise RuntimeError("Select an Armature object.")

bpy.ops.object.mode_set(mode='POSE')
pose_bones = arm_obj.pose.bones

# Example: applying to Leg or Arm bone
target_bone = pose_bones.get("Shin.L") or pose_bones.get("lower_arm.L") or (pose_bones[1] if len(pose_bones) > 1 else None)

if target_bone:
    ik_con = target_bone.constraints.new(type='IK')
    ik_con.target = arm_obj
    ik_con.chain_count = 2
    
    # Try finding an IK bone if exists
    for b in pose_bones:
        if "ik" in b.name.lower() and b.name != target_bone.name:
            ik_con.subtarget = b.name
            break
            
    print(f"Added 2-bone IK constraint to {target_bone.name}")
else:
    print("Could not find suitable limb bone for IK.")

bpy.ops.object.mode_set(mode='OBJECT')
```
