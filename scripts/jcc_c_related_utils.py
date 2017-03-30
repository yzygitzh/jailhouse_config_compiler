#coding=utf-8

"""C-Related Jailhouse Config Compiler Utils
"""

import os
import re
import subprocess
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


def get_struct_field_info(compiler_config_json):
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

    field_map = {}
    field_path = []

    def size_infer():
        struct_type_set = set([x.split(".")[0] for x in field_map])
        struct_decls = os.linesep.join(["struct %s %s_probe;" % (x, x)
                                        for x in struct_type_set])
        sizeof_asms = os.linesep.join(['asm("field_size %s %%0"::"i"(sizeof(%s_probe.%s)));' %
                                       (x, x.split(".")[0], ".".join((x.split(".")[1:])))
                                       for x in field_map])
        sizeof_source = "%s%s void f(){ %s }" % (include_c_headers(compiler_config_json),
                                                 struct_decls, sizeof_asms)
        # with open(tmp_file_path, "w") as tmp_file:
        #     tmp_file.write(sizeof_source)
        p = subprocess.Popen(["gcc", "-S", "-xc", "-o-", "-"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        asm_str_list = [x for x in p.communicate(input=sizeof_source)[0].split(os.linesep)
                        if "field_size" in x]

        for asm_str in asm_str_list:
            field_map[asm_str.split(" ")[1]]["sizeof"] = int(asm_str.split(" ")[2][1:])
        return field_map

    def visit_decl(node):
        decl_children_num = 0
        if isinstance(node, pycparser.c_ast.Decl) and node.name:
            field_path.append(node.name)
        for child in node.children():
            decl_children_num += visit_decl(child[1])
            type_name = "non_atomic_type"
        if isinstance(node, pycparser.c_ast.Decl) and node.name:
            if decl_children_num == 0:
                type_probe = node
                while not isinstance(type_probe,
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
            field_map[".".join(field_path)] = {"type_info": type_name}
            field_path.pop()
            return decl_children_num + 1
        return decl_children_num

    for struct_name in struct_dict:
        field_path = [struct_name]
        visit_decl(struct_dict[struct_name])
    size_infer()
    for field in field_map:
        print "%s %s %s" % (field, field_map[field]["type_info"], field_map[field]["sizeof"])
    return field_map


def get_macro_map(compiler_config_json):
    tmp_file_path = "%s/tmp.c" % compiler_config_json["tmp_file_dir"]

    p = subprocess.Popen(["gcc", "-dM", "-E", "-o-", tmp_file_path],
                         stdout=subprocess.PIPE)
    define_list = []
    for macro_def in p.communicate()[0].split(os.linesep):
        if len(macro_def):
            re_tmp = re.search(compiler_config_json["macro_regex"], macro_def)
            macro_id = macro_def.split()[1]
            if re_tmp is not None and re_tmp.group() == macro_id:
                define_list.append(macro_id)
    define_statements = os.linesep.join(['asm("macro_map %s %%0"::"i"(%s));' % (x, x)
                                         for x in define_list])

    define_source = "%s void f(){ %s }" % (include_c_headers(compiler_config_json),
                                           define_statements)

    with open(tmp_file_path, "w") as tmp_file:
        tmp_file.write(define_source)

    p = subprocess.Popen(["gcc", "-S", "-xc", "-o-", "-"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    asm_str_list = [x for x in p.communicate(input=define_source)[0].split(os.linesep)]
    macro_map_str_list = [x for x in asm_str_list if "macro_map" in x]
    string_decl_map = {}
    for idx, asm_str in enumerate(asm_str_list):
        if ".string" in asm_str:
            string_decl_map[asm_str_list[idx - 1][:-1]] = asm_str.split()[-1][1:-1]
    macro_map = {}
    for macro_map_str in macro_map_str_list:
        macro_val = macro_map_str.split(" ")[2][1:]
        macro_id = macro_map_str.split(" ")[1]
        if "." in macro_val:
            macro_map[macro_id] = string_decl_map[macro_val]
        else:
            macro_map[macro_id] = int(macro_val)

    for macro_id in macro_map:
        print "%s %s" % (macro_id, macro_map[macro_id])
    return macro_map