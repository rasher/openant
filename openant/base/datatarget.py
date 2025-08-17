import argparse
from abc import ABC, abstractmethod
from typing import List, Optional

from ..easy.node import Node

from ..devices import device_profiles, ANTPLUS_NETWORK_KEY
from ..devices.utilities import auto_create_device, read_json
from ..devices.common import DeviceData, AntPlusDevice
from ..devices.fitness_equipment import FitnessEquipment, Workout


class DataTarget(ABC):
    shutting_down: bool = False

    @abstractmethod
    def __init__(self, args: argparse.Namespace):
        pass

    @abstractmethod
    def write_data(self, device: AntPlusDevice, page_name: str, data: DeviceData):
        print(f"Device {device} broadcast {page_name} data: {data}")

    @abstractmethod
    def close(self):
        pass

    def run(
        self,
        node: Node,
        devices: List[AntPlusDevice],
        workouts: Optional[List[Workout]] = None,
    ):
        print(f"Starting device data importer for {devices}")

        def on_found(device):
            print(f"Device {device} found and receiving")

            if isinstance(device, FitnessEquipment):
                if workouts is not None:
                    device.start_workouts(workouts)

        for dev in devices:
            dev.on_found = lambda dev=dev: on_found(dev)
            dev.on_device_data = lambda page, page_name, data, dev=dev: self.write_data(
                dev, page_name, data
            )

        try:
            print(f"Starting {devices}, press Ctrl-C to finish")
            node.start()
        except KeyboardInterrupt:
            print("Closing ANT+ devices...")
        finally:
            self.shutting_down = True
            for dev in devices:
                dev.close_channel()

            node.stop()
            self.close()

    @classmethod
    def add_general_arguments(cls, subparser):
        subparser.add_argument(
            "device",
            choices=list(device_profiles.keys()).append("config"),
            help=f"Device {list(device_profiles.keys())} to use or 'config' for --config flag file",
        )
        subparser.add_argument(
            "--config",
            type=str,
            help=".json config file for use with 'config' type",
        )
        subparser.add_argument(
            "-I",
            "--id",
            type=int,
            default=0,
            help="Device ID, default zero will attach to first found",
        )
        subparser.add_argument(
            "-T",
            "--transtype",
            type=int,
            default=0,
            help="Transmission type, default zero will attach to first found",
        )
        subparser.add_argument(
            "-V", "--verbose", action="store_true", help="verbose output"
        )

    @classmethod
    def entry(cls, args):
        target = cls(args)

        node = Node()
        node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

        devices = []
        workouts = None

        # load from config file if config
        if args.device == "config":
            if args.config:
                config = read_json(args.config)

                if config:
                    # bit dirty but initialises classes based on snake_case string provided - TODO change when imported from module
                    for dev in config["devices"]:
                        try:
                            class_name = dev["device"]
                            device_id = dev["id"]
                            trans_type = dev["transmission_type"]
                            devices.append(
                                auto_create_device(
                                    node,
                                    device_id=device_id,
                                    device_type=class_name,
                                    trans_type=trans_type,
                                )
                            )
                        except Exception as e:
                            raise ValueError(
                                f"Failed to create device {dev} from {args.config} - is it a valid AntPlusDevice?"
                            ) from e

                    if "workouts" in config:
                        try:
                            workouts = [
                                (
                                    Workout.from_arrays(
                                        x["powers"],
                                        x["periods"],
                                        cycles=x["cycles"],
                                        loop=x["loop"],
                                    )
                                    if x["type"] == "arrays"
                                    else Workout.from_ramp(
                                        start=x["start"],
                                        stop=x["stop"],
                                        step=x["step"],
                                        period=x["period"],
                                        peak=(x["peak"] if "peak" in x else None),
                                        cycles=x["cycles"],
                                        loop=x["loop"],
                                    )
                                )
                                for x in config["workouts"]
                            ]
                        except Exception as e:
                            print(f"Failed to parse workouts in {args.config}: {e}")

                else:
                    raise ValueError("Invalid or missing config file")
            else:
                raise ValueError(
                    "--config arg with path to .json device configuation must be supplied!"
                )
        # else create DeviceType class
        else:
            devices.append(
                auto_create_device(
                    node,
                    device_id=args.id,
                    device_type=args.device,
                    trans_type=args.transtype,
                )
            )

        target.run(node=node, devices=devices, workouts=workouts)
