#coding=utf-8

"""The prototype of the compiler for new jailhouse config file format
"""

import os
import json
import yaml
import argparse
import struct

import jcc_c_utils
import jcc_struct_utils

def gen_cell_bytes(jcc_cutils, config_yaml, compiler_config_json):
    full_bytes = ""
    pre_defined_vals = {}
    jcc_sutils = jcc_struct_utils.JCC_StructUtils(jcc_cutils)

    # cpus
    cpus = config_yaml["cpus"]
    pre_defined_vals["num_cpus"] = len(cpus) * 8
    full_bytes += struct.pack("Q" * len(cpus), *cpus)

    # mem_regions
    mem_regions = config_yaml["memory_regions"]
    pre_defined_vals["num_memory_regions"] = len(mem_regions)
    for mem_region in mem_regions:
        full_bytes += jcc_sutils.pack_struct(compiler_config_json["reserved_field_types"]["memory_regions"],
                                             mem_region, pre_defined_vals)

    # fill back jailhouse_cell_desc
    full_bytes = jcc_sutils.pack_struct("jailhouse_cell_desc",
                                        config_yaml["jailhouse_cell_desc"],
                                        pre_defined_vals) + full_bytes


    """
    # cache_regions
    cache_regions = config_yaml["cache_regions"]
    for cache_region in cache_regions:
        full_bytes += struct.pack("IIBBH", *[next(iter(x.items()))[1] for x in cache_region])

    # pio_bitmap
    pio_bitmap = config_yaml["pio_bitmap"]
    bitmap_bytes = bytearray(struct.pack("B", pio_bitmap["default_value"]) * pio_bitmap["size"])
    for hole in pio_bitmap["holes"]:
        for idx in range(hole["begin"], hole["end"] + 1):
            bitmap_bytes[idx] = struct.pack("B", hole["value"])
    full_bytes += str(bitmap_bytes)
    """
    return full_bytes


def run(compiler_config_json_path, cell_config_yaml_path):
    """
    parse config file and assemble config file
    """
    with open(os.path.abspath(compiler_config_json_path), "r") as compiler_config_json_file:
        compiler_config_json = json.load(compiler_config_json_file)

    jcc_cutils = jcc_c_utils.JCC_CUtils(compiler_config_json)

    with open(os.path.abspath(cell_config_yaml_path), "r") as cell_config_yaml_file:
        cell_config_yaml = yaml.load(cell_config_yaml_file)
        print cell_config_yaml
        cell_bytes = gen_cell_bytes(jcc_cutils, cell_config_yaml, compiler_config_json)
        print len(cell_bytes)
        with open(compiler_config_json["output_path"], "wb") as output_file:
            output_file.write(cell_bytes)

def parse_args():
    """
    parse command line input
    """
    parser = argparse.ArgumentParser(description="Jailhouse config file compiler prototype")
    parser.add_argument("-c", action="store", dest="compiler_config_json_path",
                        required=True, help="path/to/compiler_config.json")
    parser.add_argument("-y", action="store", dest="cell_config_yaml_path",
                        required=True, help="path/to/cell_config.yaml")
    options = parser.parse_args()
    return options


def main():
    """
    the main function
    """
    opts = parse_args()
    run(opts.compiler_config_json_path, opts.cell_config_yaml_path)
    return


if __name__ == "__main__":
    main()
