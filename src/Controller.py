from src.Gaits import GaitController
from src.StanceController import StanceController
from src.SwingLegController import SwingController
from src.Utilities import clipped_first_order_filter
from pupper.Kinematics import four_legs_inverse_kinematics
from src.State import BehaviorState, State

import numpy as np
from transforms3d.euler import euler2mat, quat2euler
from transforms3d.quaternions import qconjugate, quat2axangle
from transforms3d.axangles import axangle2mat


class Controller:
    """Controller and planner object
    """

    def __init__(
        self,
        config,
        four_legs_inverse_kinematics,
    ):
        self.config = config

        self.smoothed_yaw = 0.0  # for REST mode only

        self.four_legs_inverse_kinematics = four_legs_inverse_kinematics

        self.previous_state = BehaviorState.REST

        # Set default for foot locations and joint angles
        self.foot_locations = (
            self.config.default_stance
            + np.array([0, 0, self.config.default_z_ref])[:, np.newaxis]
        )
        self.contact_modes = np.zeros(4)
        self.joint_angles = self.four_legs_inverse_kinematics(
            self.foot_locations, self.config
        )

        self.gait_controller = GaitController(self.config)
        self.swing_controller = SwingController(self.config)
        self.stance_controller = StanceController(self.config)

        self.hop_transition_mapping = {BehaviorState.REST: BehaviorState.HOP, BehaviorState.HOP: BehaviorState.FINISHHOP, BehaviorState.FINISHHOP: BehaviorState.REST}
        self.trot_transition_mapping = {BehaviorState.REST: BehaviorState.TROT, BehaviorState.TROT: BehaviorState.REST}
        self.activate_transition_mapping = {BehaviorState.DEACTIVATED: BehaviorState.REST, BehaviorState.REST: BehaviorState.DEACTIVATED}


    def step_gait(self, ticks, foot_locations, command):
        """Calculate the desired foot locations for the next timestep

        Returns
        -------
        Numpy array (3, 4)
            Matrix of new foot locations.
        """
        contact_modes = self.contacts(ticks)
        new_foot_locations = np.zeros((3, 4))
        for leg_index in range(4):
            contact_mode = contact_modes[leg_index]
            foot_location = foot_locations[:, leg_index]
            if contact_mode == 1:
                new_location = self.stance_controller.next_foot_location(foot_location, config, command)
            else:
                swing_proportion = (
                    self.gait_controller.subphase_time(ticks) / self.config.swing_ticks
                )
                new_location = swing_controller.next_foot_location(
                    swing_proportion,
                    foot_location,
                    leg_index,
                    command
                )
            new_foot_locations[:, leg_index] = new_location
        return new_foot_locations, contact_modes


    def run(self, state, command):
        """Steps the controller forward one timestep

        Parameters
        ----------
        controller : Controller
            Robot controller object.
        """

        ########## Update operating state based on command ######
        if command.activate_event:
            state.state = self.activate_transition_mapping[state.behavior_state]
        elif command.trot_event:
            state.state = self.trot_transition_mapping[state.state]
        elif command.hop_event:
            state.state = self.hop_transition_mapping[state.state]

        if state.state == BehaviorState.TROT:
            foot_locations, contact_modes = self.step_gait(
                state.ticks,
                state.foot_locations,
                self.config,
                command,
            )

            # Apply the desired body rotation
            # foot_locations = (
            #     euler2mat(
            #         controller.movement_reference.roll, controller.movement_reference.pitch, 0.0
            #     )
            #     @ controller.foot_locations
            # )
            # Disable joystick-based pitch and roll for trotting with IMU feedback

            # Construct foot rotation matrix to compensate for body tilt
            (roll, pitch, yaw) = quat2euler(state.quat_orientation)
            correction_factor = 0.8
            max_tilt = 0.4
            roll_compensation = correction_factor * np.clip(roll, -max_tilt, max_tilt)
            pitch_compensation = correction_factor * np.clip(pitch, -max_tilt, max_tilt)
            rmat = euler2mat(roll_compensation, pitch_compensation, 0)

            foot_locations = rmat.T @ foot_locations

            state.joint_angles = self.inverse_kinematics(
                state.foot_locations, config
            )

        elif state.state == BehaviorState.HOP:
            state.foot_locations = (
                self.config.default_stance
                + np.array([0, 0, -0.09])[:, np.newaxis]
            )
            state.joint_angles = self.inverse_kinematics(
                hop_foot_locations, config
            )

        elif state.state == BehaviorState.FINISHHOP:
            state.foot_locations = (
                self.config.default_stance
                + np.array([0, 0, -0.22])[:, np.newaxis]
            )
            state.joint_angles = inverse_kinematics(
                state.foot_locations, self.config
            )

        elif state.state == BehaviorState.REST:
            if self.previous_state != BehaviorState.REST:
                controller.smoothed_yaw = 0

            yaw_factor = -0.25
            self.smoothed_yaw += (
                self.config.dt
                * clipped_first_order_filter(
                    self.smoothed_yaw,
                    self.yaw_rate * yaw_factor,
                    1.5,
                    0.25,
                )
            )
            # Set the foot locations to the default stance plus the standard height
            state.foot_locations = (
                controller.stance_params.default_stance
                + np.array([0, 0, controller.movement_reference.z_ref])[:, np.newaxis]
            )
            # Apply the desired body rotation
            rotated_foot_locations = (
                euler2mat(
                    command.roll,
                    command.pitch,
                    self.smoothed_yaw,
                )
                @ state.foot_locations
            )
            state.joint_angles = self.four_legs_inverse_kinematics(
                rotated_foot_locations, self.config
            )

        state.ticks += 1


    def set_pose_to_default(self):
        controller.foot_locations = (
            controller.stance_params.default_stance
            + np.array([0, 0, self.config.default_z_ref])[:, np.newaxis]
        )
        controller.joint_angles = controller.four_legs_inverse_kinematics(
            state.foot_locations, self.config
        )
