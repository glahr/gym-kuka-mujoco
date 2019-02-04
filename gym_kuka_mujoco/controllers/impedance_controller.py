import os

import numpy as np
from gym import spaces
import mujoco_py

# import pdb; pdb.set_trace()
from gym_kuka_mujoco.envs.assets import kuka_asset_dir
from gym_kuka_mujoco.utils.quaternion import identity_quat, subQuat, quatIntegrate, mat2Quat
from gym_kuka_mujoco.utils.kinematics import forwardKinSite, forwardKinJacobianSite
from .base_controller import BaseController
from . import register_controller

class ImpedanceController(BaseController):
    '''
    An inverse dynamics controller that used PD gains to compute a desired acceleration.
    '''

    def __init__(self,
                 sim,
                 pos_scale=0.1,
                 rot_scale=0.5,
                 model_path='full_kuka_no_collision_no_gravity.xml',
                 site_name='peg_tip'):
        super(ImpedanceController, self).__init__(sim)

        # Create a model for control
        model_path = os.path.join(kuka_asset_dir(), model_path)
        self.model = mujoco_py.load_model_from_path(model_path)

        # Construct the action space.
        high_pos = np.inf*np.ones(3)
        low_pos = -high_pos

        high_rot = np.inf*np.ones(3)
        low_rot = -high_rot

        high = np.concatenate((high_pos, high_rot))
        low = np.concatenate((low_pos, low_rot))
        self.action_space = spaces.Box(low, high, dtype=np.float32)

        # Controller parameters.
        self.scale = np.ones(6)
        self.scale[:3] *= pos_scale
        self.scale[3:6] *= rot_scale

        self.site_name = site_name
        self.pos_set = np.zeros(3)
        self.quat_set = identity_quat.copy()

        self.stiffness = np.array([1., 1., 1., .1, .1, .1])
        self.damping = 0.

    def set_action(self, action):
        '''
        Set the setpoint.
        '''
        action = action * self.scale

        dx = action[0:3].astype(np.float64)
        dr = action[3:6].astype(np.float64)

        pos, mat = forwardKinSite(self.sim, self.site_name)
        quat = mat2Quat(mat)

        self.pos_set = pos + dx
        self.quat_set = quatIntegrate(quat, dr)

    def get_torque(self):
        '''
        Update the impedance control setpoint and compute the torque.
        '''
        # Compute the pose difference.
        pos, mat = forwardKinSite(self.sim, self.site_name)
        quat = mat2Quat(mat)
        dx = self.pos_set - pos
        dr = subQuat(self.quat_set, quat)
        dframe = np.concatenate((dx,dr))

        # Compute generalized forces from a virtual external force.
        jpos, jrot = forwardKinJacobianSite(self.sim, self.site_name)
        J = np.vstack((jpos, jrot))
        external_force = J.T.dot(self.stiffness*dframe) # virtual force on the end effector

        # Cancel other dynamics and add virtual damping using inverse dynamics.
        acc_des = -self.damping*self.sim.data.qvel
        self.sim.data.qacc[:] = acc_des
        mujoco_py.functions.mj_inverse(self.model, self.sim.data)
        id_torque = self.sim.data.qfrc_inverse[:]
        
        return id_torque + external_force

register_controller(ImpedanceController, "ImpedanceController")