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


def include_c_headers(compiler_config_json, eliminate_gcc_attr=False):
    c_headers = compiler_config_json["c_headers"]
    c_str_list = []

    # read headers and get rid of "__attribute__((packed))"'s
    for c_header_path in c_headers:
        with open(c_header_path, "r") as c_header_file:
            c_header_str = c_header_file.read()
            if eliminate_gcc_attr:
                c_header_str = c_header_str.replace("__attribute__((packed))", "")
            c_str_list.append(c_header_str)

    return os.linesep.join(c_str_list)


def get_struct_asts(compiler_config_json):
    struct_dict = {}
    tmp_file_path = "%s/tmp.c" % compiler_config_json["tmp_file_dir"]

    with open(tmp_file_path, "w") as tmp_file:
        tmp_file.write(include_c_headers(compiler_config_json, eliminate_gcc_attr=True))
    full_ast = pycparser.parse_file(tmp_file_path, use_cpp=True)

    class StructVisitor(pycparser.c_ast.NodeVisitor):
        def visit_Struct(self, node):
            if node.name not in struct_dict:
                struct_dict[node.name] = node
    StructVisitor().visit(full_ast)

    field_list = []
    field_path = []
    def visit_decl(node):
        decl_children_num = 0
        if isinstance(node, pycparser.c_ast.Decl) and node.name:
            field_path.append(node.name)
        for child in node.children():
            decl_children_num += visit_decl(child[1])
            field_name = ".".join(field_path)
            type_name = "non_atomic_type"
        if isinstance(node, pycparser.c_ast.Decl) and node.name:
            if decl_children_num == 0:
                type_probe = node
                while isinstance(type_probe,
                                 (pycparser.c_ast.IdentifierType, pycparser.c_ast.Struct)):
                    if len(type_probe.children()) > 0:
                        type_probe = type_probe.children()[0][1]
                    else:
                        type_name = "unknown_type"
                        break
                if type_name != "unknown_type":
                    if isinstance(type_probe, pycparser.c_ast.IdentifierType):
                        type_name = " ".join(type_probe.names)
                    else:
                        type_name = type_probe.name

            def sizeof_field(field_name):
                field_path = field_name.split(".")
                struct_type = field_path[0]
                rest_field = ".".join(field_path[1:])
                sizeof_statement = "%s%s" % ("struct %s probe;" % struct_type,
                                             'void f(){\
                                             asm("field_size %%0"::"i"(sizeof(probe.%s)));}'
                                             % rest_field)
                sizeof_source = "%s%s%s" % (include_c_headers(compiler_config_json),
                                            os.linesep, sizeof_statement)
                with open(tmp_file_path, "w") as tmp_file:
                    tmp_file.write(sizeof_source);
                p = subprocess.Popen(["gcc", "-S", "-xc", "-o-", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                asm_str = p.communicate(input=sizeof_source)[0]
                field_size = [int(x.split(" ")[1][1:])
                              for x in asm_str.split(os.linesep) \
                              if "field_size" in x]
                return field_size[0]

            field_list.append({
                "field_name" :field_name,
                "type_info": type_name,
                "sizeof": sizeof_field(field_name)
            })
            field_path.pop()
            return decl_children_num + 1
        return decl_children_num

    for struct_name in struct_dict:
        field_path = [struct_name]
        visit_decl(struct_dict[struct_name])
    for field in field_list:
        print "%s %s %s" % (field["field_name"], field["type_info"], field["sizeof"])


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
