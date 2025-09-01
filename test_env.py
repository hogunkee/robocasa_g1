import os
import sys
import numpy as np

import gymnasium as gym

sys.path.append('/home/hogun/Desktop/robosuite_g1')
import robosuite  # noqa: F401
sys.path.append('/home/hogun/Desktop/robocasa_g1')
import robocasa  # noqa: F401
from robocasa.utils.gym_utils import GrootRoboCasaEnv  # noqa: F401

from matplotlib import pyplot as plt
# import sys
# sys.path.append('/home/hogunkee/robocasa-gr1-tabletop-tasks')

env_id = 'g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env'
# env_id = 'g1_unified/PnPFruitToPlateSplitA_G1ArmsAndWaistDex31Hands_Env'
# env_id = 'g1_unified/PosttrainPnPNovelFromPlateToPlateSplitA_G1ArmsAndWaistDex31Hands_Env'
# env_id = 'robocasa_g1_full_dex31_hands/PnPCupToDrawerClose_G1FullDex31Hands_Env'
env = gym.make(env_id, enable_render=True)

obs, _ = env.reset()

action = {'action.left_hand': np.array([0, 0, 0, 0, 0, 0, 0]),
         'action.right_hand': np.array([0, 0, 0, 0, 0, 0, 0]),
         'action.left_arm': np.array([0, 0, 0, 0, 0, 0, 0]),
         'action.right_arm': np.array([0, 0, 0, 0, 0, 0, 0]),
         'action.waist': np.array([0, 0, 0]),
         'action.neck': np.array([0, 0, 0]),
         'action.legs': np.array([0, 1, 0, 0, 0, 0, 
                                  0, 0, 0, 0, 0, 0]),
         }

for i in range(10):
    obs, _, _, _, info = env.step(action)

view = 'backview'
img = env.env.env.env.sim.render(camera_name=view, width=640, height=480, depth=Fals, generative_textures=False)[::-1]
plt.imshow(img)
plt.show()

print()