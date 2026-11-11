from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.radar import (
    Radar, RadarData, RANGE_UNIT, ThreatLevel,
    PAGE_ERROR_DESCRIPTION_NAME

)
from openant.easy.node import Node


def main(device_id: int = 0):
    node = Node()
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    device = Radar(node, device_id=device_id)

    def on_found():
        print(f"Device {device} found and receiving")

    def on_device_data(page: int, page_name: str, data: RadarData):
        if isinstance(data, RadarData):
            data: RadarData = data
            if page_name == PAGE_ERROR_DESCRIPTION_NAME:
                print(data.error)
            line = [" "] * (0b111111 + 1)
            for target in data.active_targets:
                range_units = int(target.range / RANGE_UNIT)
                if target.range == 0.0 or target.closing_speed == 0.0 or target.threat_level == ThreatLevel.NoThreat:
                    continue
                current = line[range_units]
                if target.threat_level == ThreatLevel.VehicleApproach and current != '!':
                    line[range_units] = '#'
                elif target.threat_level == ThreatLevel.VehicleFastApproach:
                    line[range_units] = '!'
            if data.inverted_clear_targets == 0:
                pass
                line = ["-"] * (0b111111 + 1)
            print("[%s]" % "".join(line))

    device.on_found = on_found
    device.on_device_data = on_device_data

    try:
        print(f"Starting {device}, press Ctrl-C to finish")
        node.start()
    except KeyboardInterrupt:
        print("Closing ANT+ device...")
    finally:
        device.close_channel()
        node.stop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].isnumeric():
        main(int(sys.argv[1]))
    else:
        main()
