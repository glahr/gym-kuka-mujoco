from gym_kuka_mujoco.utils.kinematics import inverseKin
from gym_kuka_mujoco.utils.quaternion import identity_quat
from gym_kuka_mujoco.envs.assets import kuka_asset_dir
import os
import mujoco_py
import numpy as np

# Get the model path
model_filename = 'full_kuka_mesh_collision.xml'
model_path = os.path.join(kuka_asset_dir(), model_filename)

# Construct the model and simulation objects.
model = mujoco_py.load_model_from_path(model_path)
sim = mujoco_py.MjSim(model)

# The points to be transformed.
pos = np.array([0., 0., 0.])
body_id = model.body_name2id('kuka_link_7')

# Compute the forward kinematics
q_nom = np.zeros(7)
q_init = np.random.random(7)
body_pos = np.zeros(3)
world_pos = np.array([0., 0., 1.261])
q_opt = inverseKin(sim, q_init, q_nom, body_pos, world_pos, identity_quat, body_id)

# Visualize the solution
sim.data.qpos[:] = q_opt
sim.forward()

viewer = mujoco_py.MjViewer(sim)
while True:
    viewer.render()

print("Optimal pose: {}\n".format(q_opt))
