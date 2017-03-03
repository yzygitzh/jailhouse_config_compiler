#coding=utf-8

"""The prototype of the compiler for new jailhouse config file format
"""

import os
import struct
import argparse
import ruamel.yaml


def gen_cell_bytes(config_yaml):
    desc_byte_array = []
    full_bytes = ""

    # jailhouse_cell_desc
    jailhouse_cell_desc = config_yaml["jailhouse_cell_desc"]
    full_bytes += struct.pack("=6sH32sIIIIIIIIII", *jailhouse_cell_desc.values())

    # cpus
    cpus = config_yaml["cpus"]
    full_bytes += struct.pack("Q" * len(cpus), *cpus)

    # mem_regions
    mem_regions = config_yaml["mem_regions"]
    for mem_region in mem_regions:
        full_bytes += struct.pack("QQQQ", *mem_region.values())

    # cache_regions
    cache_regions = config_yaml["cache_regions"]
    for cache_region in cache_regions:
        full_bytes += struct.pack("IIBBH", *cache_region.values())

    # pio_bitmap
    pio_bitmap = config_yaml["pio_bitmap"]
    bitmap_bytes = bytearray(struct.pack("B", pio_bitmap["default_value"]) * pio_bitmap["size"])
    for hole in pio_bitmap["holes"]:
        for idx in range(hole["begin"], hole["end"] + 1):
            bitmap_bytes[idx] = struct.pack("B", hole["value"])
    full_bytes += str(bitmap_bytes)

    return full_bytes


def run(config_yaml_path):
    """
    parse config file and assemble config file
    """
    with open(os.path.abspath(config_yaml_path), "r") as config_file:
        config_yaml = ruamel.yaml.load(config_file, ruamel.yaml.RoundTripLoader)

        cell_bytes = gen_cell_bytes(config_yaml)
        with open("/tmp/testzone/testcell", "wb") as output_file:
            output_file.write(cell_bytes)


def parse_args():
    """
    parse command line input
    """
    parser = argparse.ArgumentParser(description="Jailhouse config file compiler prototype")
    parser.add_argument("-c", action="store", dest="config_json_path",
                        required=True, help="path/to/config_file.yaml")
    options = parser.parse_args()
    return options


def main():
    """
    the main function
    """
    opts = parse_args()
    run(opts.config_json_path)
    return


if __name__ == "__main__":
    main()
