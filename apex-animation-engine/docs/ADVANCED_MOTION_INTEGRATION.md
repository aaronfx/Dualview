# Advanced native motion integration

CPU-only independently implemented adaptations: critically damped upper-body inertial offsets, inherited transition history, native skill-feature matching, intent-specific moving posture. Native physics, foot IK, contact timing, and prior profiles are retained. Enabled in hostile facility only.

References: https://github.com/orangeduck/Spring-It-On and https://github.com/orangeduck/Motion-Matching. This is not full mocap motion matching, no external code or weights imported. AI4AnimationPy is CC BY-NC 4.0; do not import it into commercial APEX without permission. DeepMimic/ASE/CALM need a compatible rig, licensed motion data, training/inference validation; not implemented. Existing procedural physics remains authoritative. A full learned controller is a separate research milestone, not a dependency install.
