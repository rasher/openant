import argparse
import os
import uuid

import influxdb_client as idb
from influxdb_client.client.write_api import SYNCHRONOUS

from ..base.datatarget import DataTarget
from ..devices.common import DeviceData, AntPlusDevice


class InfluxTarget(DataTarget):

    def __init__(self, args: argparse.Namespace):
        self.bucket = args.bucket
        self.session_uuid: str = str(uuid.uuid4())
        self.client: idb.InfluxDBClient = self.create_connection(args)
        self.verbose: bool = args.verbose

    @staticmethod
    def create_connection(args: argparse.Namespace) -> idb.InfluxDBClient:
        # create influx connection
        client = idb.InfluxDBClient(url=args.url, token=args.token, org=args.org)

        if args.verbose:
            print(f"Created InfluxDB {client}")

        # ping client now before stream
        client.ping()
        return client

    def write_data(self, device: AntPlusDevice, page_name: str, data: DeviceData):
        super().write_data(device, page_name, data)
        InfluxTarget._write_device_data_influx(
            data,
            self.client,
            bucket=self.bucket,
            wuuid=self.session_uuid,
            device_name=str(device),
            verbose=self.verbose,
        )

    def close(self):
        self.client.close()

    @staticmethod
    def _write_device_data_influx(
        data: DeviceData,
        client: idb.InfluxDBClient,
        bucket: str,
        wuuid: str,
        device_name: str,
        verbose=True,
    ):
        host = os.uname().nodename

        if not data:
            raise ValueError("Device has no data")

        try:
            influx_tags = {
                "device": device_name,
                "uuid": wuuid,
                "host": host,
            }

            json = data.to_influx_json(tags=influx_tags)

            if verbose:
                print(f"Writing: {json}")

            point = point = idb.Point.from_dict(json)

            with client.write_api(write_options=SYNCHRONOUS) as c:
                c.write(bucket=bucket, record=point)

        except Exception as e:
            print(f"Exception during influx write: {e}")


def add_subparser(subparsers, name="influx"):
    antinflux = subparsers.add_parser(
        name,
        description=("Capture DeviceData from an ANT+ device and import to InfluxDB"),
    )
    DataTarget.add_general_arguments(antinflux)
    influx_args = antinflux.add_argument_group(f"{name} options")
    influx_args.add_argument(
        "--url",
        default="http://localhost:8086",
        type=str,
        help="URL for InfluxDB server",
    )
    influx_args.add_argument(
        "--token",
        type=str,
        help="port of InfluxDB server",
    )
    influx_args.add_argument(
        "--org",
        default="my-org",
        type=str,
        help="organisation to use on InfluxDB server",
    )
    influx_args.add_argument(
        "--bucket",
        type=str,
        default="my-bucket",
        help="influxDB bucket to write to",
    )
    antinflux.set_defaults(func=InfluxTarget.entry)
