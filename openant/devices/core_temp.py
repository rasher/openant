import logging
from enum import Enum
from typing import List, Optional

from dataclasses import dataclass, field

from ..easy.node import Node
from .common import DeviceData, AntPlusDevice, DeviceType, BatteryStatus

_logger = logging.getLogger(__name__)


class CoreTempDataQuality(Enum):
    Poor = 0
    Fair = 1
    Good = 2
    Excellent = 3

    Unused = 0xFF

    @classmethod
    def _missing_(cls, _):
        return CoreTempDataQuality.Unused


@dataclass
class CoreTemperatureData(DeviceData):
    """ANT+ core temp data"""

    quality: CoreTempDataQuality = None
    skin_temp: float = field(default=0.0, metadata={"unit": "°C"})
    core_temp: float = field(default=0.0, metadata={"unit": "°C"})
    heat_strain_index: float = field(default=0.0, metadata={"unit": "a.u."})
    reserved: int = field(default=0, metadata={"unit": ""})


class CoreTemperature(AntPlusDevice):
    def __init__(
        self,
        node: Node,
        device_id: int = 0,
        name: str = "core_temp",
        trans_type: int = 0,
    ):
        super().__init__(
            node,
            device_type=DeviceType.CoreTemp.value,
            device_id=device_id,
            period=16384,  # 2Hz
            name=name,
            trans_type=trans_type,
        )

        self._event_count = [0, 0]

        self.data = {**self.data, "core_temp": CoreTemperatureData()}

    def on_data(self, data):
        page = data[0]

        _logger.debug(f"{self} on_data: {data}")

        # General info
        if page == 0x00:
            self.data["core_temp"].quality = CoreTempDataQuality(data[2])

        # core temp main page
        elif page == 0x01:
            self._event_count[0] = self._event_count[1]
            self._event_count[1] = data[2]

            heat_strain_index_value = data[1]
            skin_temp_value = (data[3] | ((data[4] & 0xF0) << 4))
            core_temp_value = int.from_bytes(data[6:8], byteorder="little")
            reserved_value = int((data[5] << 4) | (data[4] & 0x0F))

            if skin_temp_value != 0x800:
                self.data["core_temp"].skin_temp = skin_temp_value * 0.05
            else:
                self.data["core_temp"].skin_temp = None

            if core_temp_value != 0x8000:
                self.data["core_temp"].core_temp = core_temp_value * 0.01
            else:
                self.data["core_temp"].core_temp = None

            if heat_strain_index_value != 0xFF:
                self.data["core_temp"].heat_strain_index = heat_strain_index_value * 0.1
            else:
                self.data["core_temp"].heat_strain_index = None

            if reserved_value != 0x800:
                self.data["core_temp"].reserved = reserved_value
            else:
                self.data["core_temp"].reserved = None

        self.on_device_data(page, "core_temp", self.data["core_temp"])
