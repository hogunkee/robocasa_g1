import numpy as np

from robosuite.robots import register_robot_class
from robosuite.models.robots import G1
from robosuite.models.robots.manipulators.g1_robot import (
    G1,
    G1FixedLowerBody,
    G1ArmsOnly,
)
    

@register_robot_class("LeggedRobot")
class G1FixedLowerBodyInspireHands(G1FixedLowerBody):
    @property
    def default_gripper(self):
        return {"right": "InspireRightHand", "left": "InspireLeftHand"}


@register_robot_class("LeggedRobot")
class G1FixedLowerBodyFourierHands(G1FixedLowerBody):
    @property
    def default_gripper(self):
        return {"right": "FourierRightHand", "left": "FourierLeftHand"}
    

@register_robot_class("LeggedRobot")
class G1FixedLowerBodyDex31Hands(G1FixedLowerBody):
    @property
    def default_gripper(self):
        return {"right": "Dex31RightHand", "left": "Dex31LeftHand"}


@register_robot_class("LeggedRobot")
class G1ArmsOnlyInspireHands(G1ArmsOnly):
    @property
    def default_gripper(self):
        return {"right": "InspireRightHand", "left": "InspireLeftHand"}


@register_robot_class("LeggedRobot")
class G1ArmsOnlyFourierHands(G1ArmsOnly):
    @property
    def default_gripper(self):
        return {"right": "FourierRightHand", "left": "FourierLeftHand"}
    

@register_robot_class("LeggedRobot")
class G1ArmsOnlyDex31Hands(G1ArmsOnly):
    @property
    def default_gripper(self):
        return {"right": "Dex31RightHand", "left": "Dex31LeftHand"}


@register_robot_class("LeggedRobot")
class G1ArmsAndWaist(G1):
    def __init__(self, idn=0):
        super().__init__(idn=idn)
        # self._remove_joint_actuation("leg")
        self._remove_joint_actuation("hip")
        self._remove_joint_actuation("knee")
        self._remove_joint_actuation("ankle")
        self._remove_joint_actuation("head")
        self._remove_free_joint()

    @property
    def init_qpos(self):
        init_qpos = np.array([0.0] * 17)
        right_arm_init = np.array([0.0, -0.1, 0.0, -0.2, 0.0, 0.0, 0.0])
        left_arm_init = np.array([0.0, 0.1, 0.0, -0.2, 0.0, 0.0, 0.0])
        # right_arm_init = np.array([0.0, -0.1, 0.0, -1.57, 0.0, 0.0, 0.0])
        # left_arm_init = np.array([0.0, 0.1, 0.0, -1.57, 0.0, 0.0, 0.0])
        init_qpos[3:10] = right_arm_init
        init_qpos[10:17] = left_arm_init
        print("init qpos:", init_qpos)
        return init_qpos


@register_robot_class("LeggedRobot")
class G1ArmsAndWaistFourierHands(G1ArmsAndWaist):
    pass


@register_robot_class("LeggedRobot")
class G1ArmsAndWaistDex31Hands(G1ArmsAndWaist):
    pass


@register_robot_class("LeggedRobot")
class G1Full(G1):
    def __init__(self, idn=0):
        super().__init__(idn=idn)


@register_robot_class("LeggedRobot")
class G1FullInspireHands(G1Full):
    @property
    def default_gripper(self):
        return {"right": "InspireRightHand", "left": "InspireLeftHand"}


@register_robot_class("LeggedRobot")
class G1FullFourierHands(G1Full):
    @property
    def default_gripper(self):
        return {"right": "FourierRightHand", "left": "FourierLeftHand"}
    

@register_robot_class("LeggedRobot")
class G1FullDex31Hands(G1Full):
    @property
    def default_gripper(self):
        return {"right": "Dex31RightHand", "left": "Dex31LeftHand"}
