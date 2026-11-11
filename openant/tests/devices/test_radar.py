import unittest

from openant.devices.radar import (
    RANGE_UNIT,
    CLOSING_SPEED_UNIT,
    PAGE_ERROR_DESCRIPTION,
    PAGE_RADAR_TARGETS_A,
    PAGE_RADAR_TARGETS_B,
    AntPlusMessage,
    RadarTarget,
    ThreatLevel,
    ThreatSide,
    RadarData,
    Radar, RadarErrorCode, RadarError, RadarErrorLevel,
)

TEST_PAGE_TARGETS_A = [PAGE_RADAR_TARGETS_A, 85, 0, 157, 120, 178, 119, 119]


class TestRadar(Radar):
    name: str = "testRadar"
    device_id: int = 0

    def __init__(self):
        self.data = {"radar": RadarData(
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget(),
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget()
        )}


class AntPlusMessageTest(unittest.TestCase):
    def test(self):
        msg = AntPlusMessage(TEST_PAGE_TARGETS_A)
        self.assertEqual(msg.page_number, 48, "Page number")
        for i in range(1, 8):
            self.assertEqual(msg[i], TEST_PAGE_TARGETS_A[i], "Byte %s" % i)
        # Byte 1 85 0b01010101
        self.assertEqual(msg.value(1, 1, 0, 1), 0b01)
        self.assertEqual(msg.value(1, None, 0, 1), 0b01)
        self.assertEqual(msg.value(1, None, 0, 2), 0b101)
        # Range bytes 3-5: 157, 120, 178 0b10011101, 0b01111000, 0b10110010
        # 6-bit sections, little-endian:
        # 101100.100111.100010.011101
        self.assertEqual(0b011101, msg.value(3, 5, 0, 5))
        self.assertEqual(0b100010, msg.value(3, 5, 6, 11))
        self.assertEqual(0b100111, msg.value(3, 5, 12, 17))
        self.assertEqual(0b101100, msg.value(3, 5, 18, 23))
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(msg.value(6, None, 0, 3), 0b0111)


class RadarTargetTest(unittest.TestCase):

    def test_target_1(self):
        t1 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 1)
        self.assertEqual(t1.threat_level, ThreatLevel.VehicleApproach, "T1 threat level")
        self.assertEqual(t1.threat_side, ThreatSide.NoSide, "T1 side")
        # Range bytes 3-5 - 157, 120, 178 - 0b10011101, 0b01111000, 0b10110010
        self.assertEqual(t1.range, 0b011101 * RANGE_UNIT, "T1 range")
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(t1.closing_speed, 0b0111 * CLOSING_SPEED_UNIT, "T1 closing speed")

    def test_target_2(self):
        t2 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 2)
        self.assertEqual(ThreatLevel.VehicleApproach, t2.threat_level, "T2 threat level")
        self.assertEqual(ThreatSide.NoSide, t2.threat_side, "T2 side")
        # Range bytes 3-5 - 157, 120, 178 - 0b10011101, 0b01111000, 0b10110010
        self.assertEqual(0b100010 * RANGE_UNIT, t2.range, "T2 range")
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(0b0111 * CLOSING_SPEED_UNIT, t2.closing_speed, "T2 closing speed")

    def test_str(self):
        t1 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 1)
        self.assertEqual(" 21.28 m/s @  90.625 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t1))
        t2 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 2)
        self.assertEqual(" 21.28 m/s @ 106.250 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t2))
        t3 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 3)
        self.assertEqual(" 21.28 m/s @ 121.875 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t3))
        t4 = RadarTarget.decode(AntPlusMessage(TEST_PAGE_TARGETS_A), 4)
        self.assertEqual(" 21.28 m/s @ 137.500 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t4))


class RadarTest(unittest.TestCase):
    def test_targets_a_and_b(self):
        radar = TestRadar()
        radar.on_data([PAGE_RADAR_TARGETS_A, 85, 0, 219, 71, 166, 119, 119])
        radar.on_data([PAGE_RADAR_TARGETS_B, 1, 0, 45, 0, 0, 7, 0])
        self.assertEqual(84.375, radar.data["radar"].target1.range)
        self.assertEqual(21.28, radar.data["radar"].target1.closing_speed)
        self.assertEqual(96.875, radar.data["radar"].target2.range)
        self.assertEqual(21.28, radar.data["radar"].target2.closing_speed)
        self.assertEqual(112.5, radar.data["radar"].target3.range)
        self.assertEqual(21.28, radar.data["radar"].target3.closing_speed)
        self.assertEqual(128.125, radar.data["radar"].target4.range)
        self.assertEqual(21.28, radar.data["radar"].target4.closing_speed)
        self.assertEqual(140.625, radar.data["radar"].target5.range)
        self.assertEqual(21.28, radar.data["radar"].target5.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target6.range)
        self.assertEqual(0.0, radar.data["radar"].target6.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target7.range)
        self.assertEqual(0.0, radar.data["radar"].target7.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target8.range)
        self.assertEqual(0.0, radar.data["radar"].target8.closing_speed)

    def test_less_than_5_targets(self):
        """
        When receiving 2 target_a pages without a target_b page, only targets 1-4 are active
        :return:
        """
        radar = TestRadar()
        self.assertIsNone(radar.data["radar"].active_targets)
        radar.on_data([48, 85, 0, 219, 71, 166, 119, 119])
        self.assertEqual(4, len(radar.data["radar"].active_targets))
        radar.on_data([49, 1, 0, 45, 0, 0, 7, 0])
        self.assertEqual(8, len(radar.data["radar"].active_targets))
        radar.on_data([48, 85, 0, 219, 71, 166, 119, 119])
        self.assertEqual(8, len(radar.data["radar"].active_targets))
        radar.on_data([48, 85, 0, 219, 71, 166, 119, 119])
        self.assertEqual(4, len(radar.data["radar"].active_targets))

    def test_error_page(self):
        radar = TestRadar()
        radar.on_data([PAGE_ERROR_DESCRIPTION, 0xFF, 0b10001111, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        error = radar.data["radar"].error
        self.assertIsInstance(error, RadarError)
        self.assertEqual(RadarErrorCode.Invalid, error.error_code)
        self.assertEqual(0xF, error.system_component_index)
        self.assertEqual(RadarErrorLevel.Critical, error.error_level)
        self.assertEqual(0xFFFFFFFF, error.mfg_error)
