#coding=utf-8

"""The prototype of the compiler for new jailhouse config file format
"""

import io
import os
import subprocess
import struct
import argparse
import json
import yaml
import pycparser


def include_c_headers(compiler_config_json):
    c_headers = compiler_config_json["c_headers"]
    c_str_list = []

    # read headers and get rid of "__attribute__((packed))"'s
    for c_header_path in c_headers:
        with open(c_header_path, "r") as c_header_file:
            c_header_str = c_header_file.read().replace("__attribute__((packed))", "")
            c_str_list.append(c_header_str)

    return os.linesep.join(c_str_list)


def get_struct_asts(compiler_config_json):
    struct_dict = {}
    tmp_file_path = "%s/header.c" % compiler_config_json["tmp_file_dir"]

    with open(tmp_file_path, "w") as tmp_file:
        tmp_file.write(include_c_headers(compiler_config_json))
    full_ast = pycparser.parse_file(tmp_file_path, use_cpp=True)

    class StructVisitor(pycparser.c_ast.NodeVisitor):
        def visit_Struct(self, node):
            if node.name not in struct_dict:
                struct_dict[node.name] = node

    StructVisitor().visit(full_ast)
    for struct_name in struct_dict:
        print struct_name
        # struct_dict[struct_name].show()

    field_list = []
    field_path = []
    def visit_decl(node):
        decl_children_num = 0
        if type(node) == pycparser.c_ast.Decl and node.name:
            field_path.append(node.name)
        for child in node.children():
            decl_children_num += visit_decl(child[1])
        if type(node) == pycparser.c_ast.Decl and node.name:
            if decl_children_num == 0:
                field_name = ".".join(field_path)
                type_probe = node
                type_name = ""
                while type(type_probe) not in \
                      [pycparser.c_ast.IdentifierType, pycparser.c_ast.Struct]:
                    if len(type_probe.children()) > 0:
                        type_probe = type_probe.children()[0][1]
                    else:
                        type_name = "unknown_type"
                        break
                if type_name != "unknown_type":
                    if type(type_probe) == pycparser.c_ast.IdentifierType:
                        type_name = " ".join(type_probe.names)
                    else:
                        type_name = type_probe.name
                field_list.append(" ".join([field_name, type_name]))
            field_path.pop()
            return decl_children_num + 1
        return decl_children_num

    for struct_name in struct_dict:
        field_path = [struct_name]
        visit_decl(struct_dict[struct_name])
    for field in field_list:
        print field


def get_macro_map():
    pass


def gen_cell_bytes(config_yaml):
    full_bytes = ""

    # jailhouse_cell_desc
    jailhouse_cell_desc = config_yaml["jailhouse_cell_desc"]
    full_bytes += struct.pack("=6sH32sIIIIIIIIII",
                              *[next(iter(x.items()))[1] for x in jailhouse_cell_desc])

    # cpus
    cpus = config_yaml["cpus"]
    full_bytes += struct.pack("Q" * len(cpus), *cpus)

    # mem_regions
    mem_regions = config_yaml["mem_regions"]
    for mem_region in mem_regions:
        full_bytes += struct.pack("QQQQ", *[next(iter(x.items()))[1] for x in mem_region])

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

    return full_bytes


def run(compiler_config_json_path, cell_config_yaml_path):
    """
    parse config file and assemble config file
    """
    with open(os.path.abspath(compiler_config_json_path), "r") as compiler_config_json_file:
        compiler_config_json = json.load(compiler_config_json_file)

    get_struct_asts(compiler_config_json)
    """
    with open(os.path.abspath(cell_config_yaml_path), "r") as cell_config_yaml_file:
        cell_config_yaml = yaml.load(cell_config_yaml_file)
        print cell_config_yaml
        cell_bytes = gen_cell_bytes(cell_config_yaml)
        with open(output_path, "wb") as output_file:
            output_file.write(cell_bytes)
    """

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
