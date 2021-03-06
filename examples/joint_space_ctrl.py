#!/usr/bin/env python3
from mujoco_py import load_model_from_path, MjSim, MjViewer
from gym_kuka_mujoco.utils.kinematics import forwardKin, forwardKinJacobian, forwardKinSite, forwardKinJacobianSite
import mujoco_py
import matplotlib.pyplot as plt
import numpy as np

def trajectory_gen_joints(qd, tf, n, ti=0, dt=0.002, traj=None):
    q_ref = [qd for _ in range(n_timesteps)]
    qvel_ref = [np.array([0, 0, 0, 0, 0, 0, 0]) for _ in range(n_timesteps)]
    if traj == 'spline':
        q_d = q_ref[-1]
        time = np.linspace(ti, tf, int((tf-ti)/dt))
        q0 = np.zeros(7)
        # q_ref = np.zeros((n, 7))
        for i, t in enumerate(time):
            q_ref[i] = 2*(q0-q_d)/tf**3 * t**3 - 3*(q0-q_d)/tf**2 * t**2 + q0
            # qvel_ref[i] = 6*(q0-q_d)/tf**3 * t**2 - 6*(q0-q_d)/tf**2 * t
    return q_ref, qvel_ref


def ctrl_independent_joints(error_q, error_v, error_q_int_ant):
    dt = 0.002
    error_q_int = (error_q + error_q_ant)*dt/2 + error_q_int_ant
    error_q_int_ant = error_q_int
    return np.dot(Kp, erro_q) + np.dot(Kd, erro_v) + np.dot(Ki, error_q_int)


def get_ctrl_action(controller, error_q, error_v, error_q_int_ant=0):
    if controller == 'independent_joints':
        u = ctrl_independent_joints(error_q, error_v, error_q_int_ant)
    return u, error_q_int_ant


def get_pd_matrices(kp, ki=0, kd=0, lambda_H=0):
    Kp = np.eye(7)
    for i in range(7):
        Kp[i, i] = kp * (7 - i)

    Kd = np.eye(7)
    for i in range(7):
        if i == 6:
            Kd[i, i] = Kp[i, i] ** 0.005 * (7 - i)
        elif i == 4:
            Kd[i, i] = Kp[i, i] ** 0.1 * (10 - i)
        else:
            Kd[i, i] = Kp[i, i] ** 0.25 * (10 - i)

    Ki = np.eye(7)
    for i in range(7):
        Ki[i, i] = 0.9*Kp[i,i]*Kd[i,i]/lambda_H
    return Kp, Kd, Ki


if __name__ == '__main__':

    simulate = True

    model = load_model_from_path(
        "/home/glahr/mujoco_gym/gym-kuka-mujoco/gym_kuka_mujoco/envs/assets/full_kuka_all_joints.xml")

    sim = MjSim(model)

    if simulate:
        viewer = MjViewer(sim)

    tf = 1
    n_timesteps = 3000
    controller_type = 'independent_joints'
    if controller_type == 'independent_joints':
        kp = 10
        lambda_H = 11
        error_q_int_ant = 0
        Kp, Kd, Ki = get_pd_matrices(kp=kp, ki=0, lambda_H=lambda_H)
    k = 1

    # qd = np.array([0, 0.461, 0, -0.817, 0, 0.69, 0])
    # qd = np.array([0, 0, 0, 0, 0, 0, 0])
    qd = np.array([0, 0, 0, -np.pi/2, -np.pi/2, 0, 0])
    q_ref, qvel_ref = trajectory_gen_joints(qd, tf, n_timesteps, traj='step')
    q_log = np.zeros((n_timesteps, 7))
    time_log = np.zeros((n_timesteps, 1))
    H = np.zeros(sim.model.nv * sim.model.nv)

    eps = 0.05

    mass_links = sim.model.body_mass[4:11]
    name_body = [sim.model.body_id2name(i) for i in range(4, 11)]
    name_tcp = sim.model.site_id2name(1)
    name_ft_sensor = sim.model.site_id2name(2)
    jac_shape = (3, sim.model.nv)
    C = np.zeros(7)

    sim.forward()

    max_trace = 0
    error_q_ant = 0
    erro_q = q_ref[0] - sim.data.qpos
    qd = np.array([0, 0, 0, 0, 0, 0, 0])

    while True:

        if (np.absolute(erro_q) < eps).all():
            qd = np.array([0, 0, 3/2*np.pi/2, 0, 0, -np.pi/2, 0])
            # print("tolerancia " + str(sim.data.time))

        qpos = sim.data.qpos
        qvel = sim.data.qvel
        erro_q = q_ref[k] + qd - qpos
        erro_v = qvel_ref[k] - qvel

        # inertia matrix H
        mujoco_py.functions.mj_fullM(sim.model, H, sim.data.qM)
        H_ = H.reshape(sim.model.nv, sim.model.nv)
        current_trace = np.trace(H_)
        if current_trace > max_trace:
            max_trace = current_trace
        # internal forces: Coriolis + gravitational
        C = sim.data.qfrc_bias

        u, error_q_int_ant = get_ctrl_action(controller_type, erro_q, erro_v, error_q_int_ant)

        sim.data.ctrl[:] = u

        sim.step()
        if simulate:
            viewer.render()
        k += 1
        if k >= n_timesteps:  # and os.getenv('TESTING') is not None:
            break

        q_log[k] = qpos
        time_log[k] = sim.data.time
        error_q_ant = erro_q

    plt.plot(time_log, q_log)
    plt.plot(time_log, [q_r for q_r in q_ref], 'k--')
    plt.legend(['q'+str(i+1) for i in range(7)])
    plt.show()
    print("biggest trace = ", max_trace)
