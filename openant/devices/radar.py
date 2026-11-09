import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .common import DeviceData, AntPlusDevice, DeviceType
from ..easy.node import Node

PAGE_DEVICE_STATUS = 0x01 # 1
PAGE_DEVICE_STATUS_NAME = "device_status"
PAGE_RADAR_TARGETS_A = 0x30 # 48
PAGE_RADAR_TARGETS_A_NAME = "radar_targets_a"
PAGE_RADAR_TARGETS_B = 0x31 # 49
PAGE_RADAR_TARGETS_B_NAME = "radar_targets_b"

RANGE_UNIT = 3.125  # m
CLOSING_SPEED_UNIT = 3.04  # m/s

_logger = logging.getLogger(__name__)


class AntPlusMessage:
    def __init__(self, data: bytes|list[int]):
        self.data = data

    def __iter__(self):
        yield iter(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def value(self, bytes_from: int, bytes_to: int | None, bits_from: int, bits_to: int) -> int:
        """
        Retrieve a value from a message. All parameters are 0-indexed and inclusive, matching
        ANT specification documents.
        :param bytes_from int: Start byte
        :param bytes_to int|None: End byte. Pass None or equal to `bytes_from` to read from one byte
        :param bits_from int: First bit
        :param bits_to int: last bit
        """
        if bytes_from == bytes_to or bytes_to is None:
            v = self.data[bytes_from]
            bytes_to = bytes_from
        else:
            v = int.from_bytes(self.data[slice(bytes_from, bytes_to + 1)], byteorder="big")
        mask = (1 << ((bits_to + 1) - bits_from)) - 1
        num_bytes = bytes_to + 1 - bytes_from
        rshift = 8 * num_bytes - (bits_to + 1)
        return (v >> rshift) & mask

    @property
    def page_number(self) -> int:
        return self.data[0]


class ThreatLevel(Enum):
    NoThreat = 0
    VehicleApproach = 1
    VehicleFastApproach = 2
    Reserved = 3

    @classmethod
    def _missing_(cls, value: object) -> Any:
        return ThreatLevel.Reserved


class DeviceState(Enum):
    Broadcasting = 0
    ShutdownRequested = 1
    ShutdownAborted = 2
    ShutdownForced = 3

    @classmethod
    def _missing_(cls, value: object) -> Any:
        return DeviceState.Broadcasting


class ThreatSide(Enum):
    NoSide = 0
    Right = 1
    Left = 2
    Reserved = 3

    @classmethod
    def _missing_(cls, value: object) -> Any:
        return ThreatSide.NoSide


@dataclass
class RadarTarget:
    threat_level: ThreatLevel = field(default=ThreatLevel.NoThreat)
    threat_side: ThreatSide = field(default=ThreatSide.NoSide)
    range: float = field(default=0.0, metadata={"unit": "m"})
    closing_speed: float = field(default=0.0, metadata={"unit": "m/s"})

    @classmethod
    def decode(cls, data: AntPlusMessage, target_no):
        target_no = target_no % 4
        # _logger.warning("Decode %d from %r", target_no, data)
        idx = (target_no - 1)
        offset = idx * 2
        threat_level = ThreatLevel(data.value(1, None, 0 + offset, 1 + offset))
        threat_side = ThreatSide(data.value(2, None, 0 + offset, 1 + offset))
        offset = idx * 6
        range = data.value(3, 5, 0 + offset, 5 + offset) * RANGE_UNIT
        closing_speed = 0.0
        if target_no <= 2:
            speed_byte = 6
            offset = (idx % 2) * 4
        else:
            speed_byte = 7
            offset = (idx % 2) * 4
        closing_speed = data.value(speed_byte, None, 0 + offset, 3 + offset) * CLOSING_SPEED_UNIT

        return cls(threat_level, threat_side, range, closing_speed)

    def __str__(self) -> str:
        return "{:6.2f} m/s @ {:7.3f} m - {} {}".format(self.closing_speed, self.range, self.threat_level,
                                                        self.threat_side)


@dataclass
class RadarData(DeviceData):
    target1: RadarTarget
    target2: RadarTarget
    target3: RadarTarget
    target4: RadarTarget
    target5: RadarTarget
    target6: RadarTarget
    target7: RadarTarget
    target8: RadarTarget
    device_state: DeviceState = DeviceState.Broadcasting
    inverted_clear_targets: int = 1

    def to_influx_json(self, tags: dict):
        influx_json = super().to_influx_json(self, tags)
        return influx_json

    def __str__(self) -> str:
        return "\n".join(map(str, [self.target1, self.target2, self.target3, self.target4,
                                   self.target5, self.target6, self.target7, self.target8]))

    @property
    def targets(self) -> list[RadarTarget]:
        return [self.target1, self.target2, self.target3, self.target4, self.target5, self.target6,
                           self.target7, self.target8]


class Radar(AntPlusDevice):
    def __init__(
            self,
            node: Node,
            device_id: int = 0,
            name: str = "radar",
            trans_type: int = 0,
    ):
        super().__init__(
            node,
            rf_freq=57,
            trans_type=trans_type,
            device_type=DeviceType.Radar.value,
            device_id=device_id,
            period=4084,  # ~8Hz
            name=name,
        )

        self._event_count = [0, 0]

        self.data = {**self.data, "radar": RadarData(
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget(),
            RadarTarget(), RadarTarget(), RadarTarget(), RadarTarget()
        )}

    def open_channel(self, extended=False, channel_type=None, ext_assign: Optional[int] = 0x00):
        _logger.warning("Opening channel extended=%s channel_type=%s ext_assign=%s", extended, channel_type, ext_assign)
        return super().open_channel(extended, channel_type, ext_assign)

    def on_data(self, data):
        _logger.debug("%s on_data: %s", self, data)
        page = AntPlusMessage(data)

        if page.page_number == PAGE_RADAR_TARGETS_A:
            self.data["radar"].target1 = RadarTarget.decode(page, 1)
            self.data["radar"].target2 = RadarTarget.decode(page, 2)
            self.data["radar"].target3 = RadarTarget.decode(page, 3)
            self.data["radar"].target4 = RadarTarget.decode(page, 4)
            self.on_device_data(page.page_number, PAGE_RADAR_TARGETS_A_NAME, self.data["radar"])
        elif page.page_number == PAGE_RADAR_TARGETS_B:
            self.data["radar"].target5 = RadarTarget.decode(page, 1)
            self.data["radar"].target6 = RadarTarget.decode(page, 2)
            self.data["radar"].target7 = RadarTarget.decode(page, 3)
            self.data["radar"].target8 = RadarTarget.decode(page, 4)
            self.on_device_data(page.page_number, PAGE_RADAR_TARGETS_B_NAME, self.data["radar"])
        elif page.page_number == PAGE_DEVICE_STATUS:
            _logger.debug("Device status: %r", data)
            self.data["radar"].device_state = page.value(1, None, 0, 1)
            self.data["radar"].inverted_clear_targets = page.value(7, None, 0, 1)
            self.on_device_data(page.page_number, PAGE_DEVICE_STATUS_NAME, self.data["radar"])
        elif page.page_number in (0x50, 0x51, 0x52):
            # Common pages handled centrally
            pass
        else:
            raise Exception("Unknown page: %d: %r" % (page.page_number, data))
