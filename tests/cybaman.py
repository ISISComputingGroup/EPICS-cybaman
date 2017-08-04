import unittest
from unittest import skipIf

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import IOCRegister
from utils.testing import get_running_lewis_and_ioc

from time import sleep


class CybamanTests(unittest.TestCase):
    """
    Tests for the cybaman IOC.
    """

    AXES = ["A", "B", "C"]
    test_positions = [-200, -1.23, 0, 180.0]

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("cybaman")

        self.ca = ChannelAccess(20)
        self.ca.wait_for("CYBAMAN_01:INITIALIZE", timeout=30)

        # Initialize the device, do this in setup to avoid doing it in every test
        self.ca.set_pv_value("CYBAMAN_01:INITIALIZE", 1)
        self.ca.assert_that_pv_is("CYBAMAN_01:INITIALIZED", "TRUE")

    def test_WHEN_ioc_is_started_THEN_ioc_is_not_disabled(self):
        self.ca.assert_that_pv_is("CYBAMAN_01:DISABLE", "COMMS ENABLED")

    @skipIf(IOCRegister.uses_rec_sim, "Uses lewis backdoor command")
    def test_WHEN_position_setpoints_are_set_via_backdoor_THEN_positions_move_towards_setpoints(self):
        for axis in self.AXES:
            for pos in self.test_positions:
                self._lewis.backdoor_set_on_device("{}_setpoint".format(axis.lower()), pos)
                self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis), pos, tolerance=0.01)

    @skipIf(IOCRegister.uses_rec_sim, "Uses lewis backdoor command")
    def test_GIVEN_home_position_is_set_WHEN_home_pv_is_set_THEN_position_moves_towards_home(self):
        for axis in self.AXES:
            for pos in self.test_positions:
                self._lewis.backdoor_set_on_device("home_position_axis_{}".format(axis.lower()), pos)
                self.ca.set_pv_value("CYBAMAN_01:{}:HOME".format(axis), 1)
                self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis), pos, tolerance=0.01)

    @skipIf(IOCRegister.uses_rec_sim, "Uses lewis backdoor command")
    def test_GIVEN_a_device_in_some_other_state_WHEN_reset_command_is_sent_THEN_device_is_reset_to_original_state(self):

        modifier = 12.34

        # Reset cybaman
        self.ca.set_pv_value("CYBAMAN_01:RESET", 1)
        # Allow time for cybaman to reset
        sleep(1)
        self.ca.set_pv_value("CYBAMAN_01:INITIALIZE", 1)
        # Wait for device to initialize properly and values to propagate before grabbing them
        sleep(10)

        original = {}
        for axis in self.AXES:
            original[axis] = float(self.ca.get_pv_value("CYBAMAN_01:{}".format(axis.upper())))

            # Set both value and setpoint to avoid the device moving back towards the setpoint
            self._lewis.backdoor_set_on_device("{}_setpoint".format(axis.lower()), original[axis] + modifier)
            self._lewis.backdoor_set_on_device("{}".format(axis.lower()), original[axis] + modifier)

            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), original[axis] + modifier, tolerance=0.001)

        # Reset cybaman
        self.ca.set_pv_value("CYBAMAN_01:RESET", 1)

        # Check that a, b and c values are now at original values
        for axis in self.AXES:
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), original[axis], tolerance=0.001)

    def test_GIVEN_a_device_in_initialized_state_WHEN_setpoints_are_sent_THEN_device_goes_to_setpoint(self):
        for axis in self.AXES:
            for pos in self.test_positions:
                self.ca.set_pv_value("CYBAMAN_01:{}:SP".format(axis.upper()), pos)
                self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), pos)

    @skipIf(IOCRegister.uses_rec_sim, "Uses lewis backdoor command")
    def test_GIVEN_a_device_with_a_setpoint_less_than_minus_150_WHEN_homed_THEN_setpoint_is_set_to_minus_150_before_home(self):
        for axis in self.AXES:
            # Ensure home position is known
            self._lewis.backdoor_set_on_device("home_position_axis_{}".format(axis.lower()), 100)

            # Ensure setpoint and readback are less than -150
            self.ca.set_pv_value("CYBAMAN_01:{}:SP".format(axis.upper()), -155)
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), -155, tolerance=0.01)

            # Tell axis to home
            self.ca.set_pv_value("CYBAMAN_01:{}:HOME".format(axis.upper()), 1)

            # Ensure that setpoint is updated to -150 before home
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}:SP".format(axis.upper()), -150, tolerance=0.01)

            # Let device actually reach home position
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), 100)

    @skipIf(IOCRegister.uses_rec_sim, "Uses lewis backdoor command")
    def test_GIVEN_a_device_with_a_setpoint_more_than_minus_150_WHEN_homed_THEN_setpoint_is_not_set_before_home(self):
        for axis in self.AXES:
            # Ensure home position is known
            self._lewis.backdoor_set_on_device("home_position_axis_{}".format(axis.lower()), 100)

            # Ensure setpoint and readback are more than -150
            self.ca.set_pv_value("CYBAMAN_01:{}:SP".format(axis.upper()), -145)
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), -145, tolerance=0.01)

            # Tell axis to home
            self.ca.set_pv_value("CYBAMAN_01:{}:HOME".format(axis.upper()), 1)

            # Ensure that setpoint has not been updated
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}:SP".format(axis.upper()), -145, tolerance=0.01)

            # Let device actually reach home position
            self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), 100)

    def test_GIVEN_a_device_at_a_specific_position_WHEN_setpoint_is_updated_THEN_tm_val_is_calculated_correctly(self):

        test_cases = (
            # No change in setpoint, TM val should be 4000
            {"old_pos": (-1, -2, -3),  "axis_to_change": "A", "new_setpoint": -1, "expected_tm_val": 4000},
            # Test case provided from flowchart specification
            {"old_pos": (0, 0, 0),     "axis_to_change": "A", "new_setpoint": 30, "expected_tm_val": 6000},
            # Test case provided from flowchart specification
            {"old_pos": (11, -5, 102), "axis_to_change": "C", "new_setpoint": 50, "expected_tm_val": 10000},
            # Very small change, TM val should be 4000
            {"old_pos": (10, 20, 30),  "axis_to_change": "B", "new_setpoint": 21, "expected_tm_val": 4000},
        )

        for case in test_cases:
            # Ensure original position is what it's meant to be
            for axis, setpoint in zip(self.AXES, case["old_pos"]):
                self.ca.set_pv_value("CYBAMAN_01:{}:SP".format(axis.upper()), setpoint)
                self.ca.assert_that_pv_is_number("CYBAMAN_01:{}".format(axis.upper()), setpoint, tolerance = 0.01)

            # Change the relevant axis to a new setpoint
            self.ca.set_pv_value("CYBAMAN_01:{}:SP".format(case["axis_to_change"].upper()), case["new_setpoint"])

            # Assert that the TM val calculation record contains the correct value
            # Tolerance is 1001 because rounding errors would get multiplied by 1000
            self.ca.assert_that_pv_is_number("CYBAMAN_01:_CALC_TM_AND_SET", case["expected_tm_val"], tolerance=1001)

    def test_GIVEN_an_initialized_ioc_WHEN_reset_pv_is_processed_THEN_ioc_is_still_initialized(self):
        self.ca.set_pv_value("CYBAMAN_01:RESET", 1)
        self.ca.assert_that_pv_is("CYBAMAN_01:INITIALIZED", "TRUE")

    def test_GIVEN_an_initialized_ioc_WHEN_stop_and_then_initialize_pvs_are_processed_THEN_initialized_pv_is_false_then_true(self):
        self.ca.set_pv_value("CYBAMAN_01:STOP", 1)
        self.ca.assert_that_pv_is("CYBAMAN_01:INITIALIZED", "FALSE")
        self.ca.set_pv_value("CYBAMAN_01:INITIALIZE", 1)
        self.ca.assert_that_pv_is("CYBAMAN_01:INITIALIZED", "TRUE")


