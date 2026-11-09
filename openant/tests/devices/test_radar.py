import unittest

from openant.devices.radar import (
    RANGE_UNIT,
    CLOSING_SPEED_UNIT,
    AntPlusMessage,
    RadarTarget,
    ThreatLevel,
    ThreatSide,
    RadarData,
    Radar,
)

TEST_PAGE = [48, 85, 0, 157, 120, 178, 119, 119]


class AntPlusMessageTest(unittest.TestCase):
    def test(self):
        msg = AntPlusMessage(TEST_PAGE)
        self.assertEqual(msg.page_number, 48, "Page number")
        for i in range(1, 8):
            self.assertEqual(msg[i], TEST_PAGE[i], "Byte %s" % i)
        # Byte 1 85 0b01010101
        self.assertEqual(msg.value(1, 1, 0, 1), 0b01)
        self.assertEqual(msg.value(1, None, 0, 1), 0b01)
        # Range bytes 3-5: 157, 120, 178 0b10011101, 0b01111000, 0b10110010
        self.assertEqual(msg.value(3, 5, 0, 5), 0b100111)
        self.assertEqual(msg.value(3, 5, 6, 11), 0b010111)
        self.assertEqual(msg.value(3, 5, 12, 17), 0b100010)
        self.assertEqual(msg.value(3, 5, 18, 23), 0b110010)
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(msg.value(6, None, 0, 3), 0b0111)


class RadarTargetTest(unittest.TestCase):

    def test_target_1(self):
        t1 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 1)
        self.assertEqual(t1.threat_level, ThreatLevel.VehicleApproach, "T1 threat level")
        self.assertEqual(t1.threat_side, ThreatSide.NoSide, "T1 side")
        # Range bytes 3-5 - 157, 120, 178 - 0b10011101, 0b01111000, 0b10110010
        self.assertEqual(t1.range, 0b100111 * RANGE_UNIT, "T1 range")
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(t1.closing_speed, 0b0111 * CLOSING_SPEED_UNIT, "T1 closing speed")

    def test_target_2(self):
        t2 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 2)
        self.assertEqual(ThreatLevel.VehicleApproach, t2.threat_level, "T2 threat level")
        self.assertEqual(ThreatSide.NoSide, t2.threat_side, "T2 side")
        # Range bytes 3-5 - 157, 120, 178 - 0b10011101, 0b01111000, 0b10110010
        self.assertEqual(0b010111 * RANGE_UNIT, t2.range, "T2 range")
        # Speed bytes 6-7 - 119, 119 - 0b01110111, 0b01110111
        self.assertEqual(0b0111 * CLOSING_SPEED_UNIT, t2.closing_speed, "T2 closing speed")

    def test_str(self):
        t1 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 1)
        self.assertEqual(" 21.28 m/s @ 121.875 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t1))
        t2 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 2)
        self.assertEqual(" 21.28 m/s @  71.875 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t2))
        t3 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 3)
        self.assertEqual(" 21.28 m/s @ 106.250 m - ThreatLevel.VehicleApproach ThreatSide.NoSide", str(t3))
        t4 = RadarTarget.decode(AntPlusMessage(TEST_PAGE), 4)
        self.assertEqual(" 21.28 m/s @   0.000 m - ThreatLevel.NoThreat ThreatSide.NoSide", str(t4))


class TestRadar(Radar):
    name: str = "testRadar"
    device_id: int = 0
    def __init__(self):
        self.data = {"radar": RadarData(
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget(),
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget()
        )}


class RadarTest(unittest.TestCase):
    def test(self):
        radar = TestRadar()
        radar.on_data([48, 85, 0, 219, 71, 166, 119, 119])
        radar.on_data([49, 1, 0, 45, 0, 0, 7, 0])
        self.assertEqual(168.75, radar.data["radar"].target1.range)
        self.assertEqual(21.28, radar.data["radar"].target1.closing_speed)
        self.assertEqual(162.5, radar.data["radar"].target2.range)
        self.assertEqual(21.28, radar.data["radar"].target2.closing_speed)
        self.assertEqual(93.75, radar.data["radar"].target3.range)
        self.assertEqual(21.28, radar.data["radar"].target3.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target4.range)
        self.assertEqual(21.28, radar.data["radar"].target4.closing_speed)
        self.assertEqual(34.375, radar.data["radar"].target5.range)
        self.assertEqual(0.0, radar.data["radar"].target5.closing_speed)
        self.assertEqual(50.0, radar.data["radar"].target6.range)
        self.assertEqual(21.28, radar.data["radar"].target6.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target7.range)
        self.assertEqual(0.0, radar.data["radar"].target7.closing_speed)
        self.assertEqual(0.0, radar.data["radar"].target8.range)
        self.assertEqual(21.28, radar.data["radar"].target8.closing_speed)
