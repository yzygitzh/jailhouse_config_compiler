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
    meta_type = compiler_config_json["meta_type"]
    pre_defined_vals = {}
    jcc_sutils = jcc_struct_utils.JCC_StructUtils(jcc_cutils)

    def gen_region_bytes(region_name, pre_defined_val_name):
        if region_name in config_yaml:
            regions = config_yaml[region_name]
            pre_defined_vals["%s.%s" % (meta_type, pre_defined_val_name)] = len(regions)
            ret_bytes = ""
            for region in regions:
                ret_bytes += jcc_sutils.pack_struct(compiler_config_json["reserved_field_types"][region_name],
                                                    region, [])
            return ret_bytes
        else:
            return ""

    # cpus
    cpu_bytes = ""
    if "cpus" in config_yaml:
        cpus = config_yaml["cpus"]
        pre_defined_vals["%s.%s" % (meta_type, "cpu_set_size")] = len(cpus) * 8
        cpu_bytes = struct.pack("Q" * len(cpus), *cpus)

    # memory_regions
    memory_bytes = gen_region_bytes("memory_regions", "num_memory_regions")
    # cache_regions
    cache_bytes = gen_region_bytes("cache_regions", "num_cache_regions")
    # irqchips
    irqchip_bytes = gen_region_bytes("irqchips", "num_irqchips")

    # pio_bitmap
    pio_bitmap_bytes = ""
    if "pio_bitmap" in config_yaml:
        pio_bitmap = config_yaml["pio_bitmap"]
        pre_defined_vals["%s.%s" % (meta_type, "pio_bitmap_size")] = pio_bitmap["size"]
        bitmap_bytes = bytearray(struct.pack("B", pio_bitmap["default_value"]) * pio_bitmap["size"])
        for hole in pio_bitmap["holes"]:
            for idx in range(hole["begin"], hole["end"] + 1):
                bitmap_bytes[idx] = struct.pack("B", hole["value"])
        pio_bitmap_bytes = str(bitmap_bytes)

    # pci_devices
    pci_device_bytes = gen_region_bytes("pci_devices", "num_pci_devices")
	# pci_caps
    pci_caps_bytes = gen_region_bytes("pci_caps", "num_pci_caps")

    # fill back meta_type
    meta_bytes = jcc_sutils.pack_struct(meta_type,
                                        config_yaml[meta_type],
                                        pre_defined_vals)
    return meta_bytes + cpu_bytes + memory_bytes + cache_bytes + irqchip_bytes + \
           pio_bitmap_bytes + pci_device_bytes + pci_caps_bytes


def run(compiler_config_json_path, cell_config_yaml_path):
    """
    parse config file and assemble config file
    """
    with open(os.path.abspath(compiler_config_json_path), "r") as compiler_config_json_file:
        compiler_config_json = json.load(compiler_config_json_file)

    jcc_cutils = jcc_c_utils.JCC_CUtils(compiler_config_json)

    with open(os.path.abspath(cell_config_yaml_path), "r") as cell_config_yaml_file:
        cell_config_yaml = yaml.load(cell_config_yaml_file)
        # print cell_config_yaml
        cell_bytes = gen_cell_bytes(jcc_cutils, cell_config_yaml, compiler_config_json)
        # print len(cell_bytes)
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
