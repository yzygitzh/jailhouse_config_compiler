#coding=utf-8

"""C-Related Jailhouse Config Compiler Utils
"""

import os
import re
import json
import subprocess
import pycparser

class JCC_CUtils():
    def __init__(self, compiler_config_json):
        self.__root_name_info = self.__get_struct_field_info(compiler_config_json)
        self.__macro_map = self.__get_macro_map(compiler_config_json)
        # print json.dumps(self.__root_name_info, indent=2)
        # print self.__macro_map

    def __include_c_headers(self, compiler_config_json, eliminate_gcc_attr=False):
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


    def __get_struct_field_info(self, compiler_config_json):
        struct_dict = {}
        union_dict = {}
        anonymous_struct_dict = {}
        anonymous_union_dict = {}

        tmp_file_path = "%s/tmp.c" % compiler_config_json["tmp_file_dir"]

        with open(tmp_file_path, "w") as tmp_file:
            tmp_file.write(self.__include_c_headers(compiler_config_json, eliminate_gcc_attr=True))
        full_ast = pycparser.parse_file(tmp_file_path, use_cpp=True)

        class StructVisitor(pycparser.c_ast.NodeVisitor):
            def visit_Struct(self, node):
                if node.name not in struct_dict and node.name:
                    struct_dict[node.name] = node
            def visit_Union(self, node):
                if node.name not in union_dict and node.name:
                    union_dict[node.name] = node
        StructVisitor().visit(full_ast)
        # full_ast.show()

        field_info_list = []
        anonymous_field_info_list = []
        field_path = []

        def size_infer():
            struct_decls = os.linesep.join(["struct %s %s_probe;" % (x, x)
                                            for x in struct_dict])
            union_decls = os.linesep.join(["union %s %s_probe;" % (x, x)
                                           for x in union_dict])
            sizeof_asms = os.linesep.join(['asm("field_size %s %%0"::"i"(sizeof(%s_probe.%s)));' %
                                           (x["field_name"], x["field_name"].split(".")[0],
                                            ".".join((x["field_name"].split(".")[1:])))
                                           for x in field_info_list])
            sizeof_source = "%s%s%s void f(){ %s }" % \
                            (self.__include_c_headers(compiler_config_json),
                             struct_decls, union_decls, sizeof_asms)
            with open(tmp_file_path, "w") as tmp_file:
                tmp_file.write(sizeof_source)
            p = subprocess.Popen(["gcc", "-S", "-xc", "-o-", "-"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            asm_str_list = [x for x in p.communicate(input=sizeof_source)[0].split(os.linesep)
                            if "field_size" in x]

            size_dict = {}
            for idx, asm_str in enumerate(asm_str_list):
                sizeof = int(asm_str.split(" ")[2][1:])
                field_info_list[idx]["sizeof"] = sizeof
                size_dict[field_info_list[idx]["field_name"]] = sizeof
            for idx, field_info in enumerate(anonymous_field_info_list):
                origin_name = field_info["field_name"].split("#")[1].replace("$", ".")
                anonymous_field_info_list[idx]["sizeof"] = size_dict[origin_name]
            return field_info_list

        def visit_decl(node, detect_anonymous_type):
            decl_children_num = 0

            if isinstance(node, pycparser.c_ast.Decl) and node.name:
                field_path.append(node.name)

            for child in node.children():
                if isinstance(node, pycparser.c_ast.Union) and \
                   node.name is None and detect_anonymous_type:
                    anonymous_union_dict["anonymous_union_in#%s" % "$".join(field_path)] = node
                decl_children_num += visit_decl(child[1], detect_anonymous_type)

            if isinstance(node, pycparser.c_ast.Decl) and node.name:
                type_probe = node
                while not isinstance(type_probe,
                                     (pycparser.c_ast.IdentifierType,
                                      pycparser.c_ast.Struct,
                                      pycparser.c_ast.Union)):
                    if len(type_probe.children()) > 0:
                        type_probe = type_probe.children()[0][1]
                if isinstance(type_probe, pycparser.c_ast.IdentifierType):
                    type_name = " ".join(type_probe.names)
                elif isinstance(type_probe, pycparser.c_ast.Struct) and type_probe.name is None:
                    # anonymous struct. maybe anonymous type in anonymous type
                    type_name = "$".join(field_path)
                    if "anonymous_struct#" not in type_name:
                        type_name = "anonymous_struct#" + type_name
                    if detect_anonymous_type:
                        anonymous_struct_dict[type_name] = type_probe
                else:
                    type_name = type_probe.name
                append_load = {
                    "type_info": type_name,
                    "field_name": ".".join(field_path),
                }
                if detect_anonymous_type:
                    field_info_list.append(append_load)
                else:
                    anonymous_field_info_list.append(append_load)
                field_path.pop()
                return decl_children_num + 1
            return decl_children_num

        # expand fields
        for struct_name in struct_dict:
            field_path = [struct_name]
            visit_decl(struct_dict[struct_name], True)
        for union_name in union_dict:
            field_path = [union_name]
            visit_decl(union_dict[union_name], True)
        # expand anonymous fields
        for anonymous_struct_name in anonymous_struct_dict:
            field_path = [anonymous_struct_name]
            visit_decl(anonymous_struct_dict[anonymous_struct_name], False)
        for anonymous_union_name in anonymous_union_dict:
            field_path = [anonymous_union_name]
            visit_decl(anonymous_union_dict[anonymous_union_name], False)
        size_infer()

        field_info_list += anonymous_field_info_list
        ret_dict = {"struct": {}, "union": {}}
        for field in field_info_list:
            # get rid of redundant field information
            if len(field["field_name"].split(".")) > 2:
                continue
            root_name = field["field_name"].split(".")[0]
            if root_name in struct_dict or root_name in anonymous_struct_dict:
                if root_name not in ret_dict["struct"]:
                    ret_dict["struct"][root_name] = []
                ret_dict["struct"][root_name].append(field)
            elif root_name in union_dict or root_name in anonymous_union_dict:
                if root_name not in ret_dict["union"]:
                    ret_dict["union"][root_name] = []
                ret_dict["union"][root_name].append(field)
        return ret_dict


    def __get_macro_map(self, compiler_config_json):
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

        define_source = "%s void f(){ %s }" % (self.__include_c_headers(compiler_config_json),
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
        return macro_map

    def is_a_struct(self, struct_name):
        return struct_name in self.__root_name_info["struct"]

    def is_a_union(self, union_name):
        return union_name in self.__root_name_info["union"]

    def is_a_macro(self, macro_id):
        return macro_id in self.__macro_map

    def get_macro_val(self, macro_id):
        return self.__macro_map[macro_id]

    def get_struct_info(self, struct_name):
        if struct_name in self.__root_name_info["struct"]:
            return self.__root_name_info["struct"][struct_name]
        else:
            return self.__root_name_info["union"][struct_name]

    def get_struct_size(self, struct_name):
        return sum([x["sizeof"] for x in self.get_struct_info(struct_name)])

    def get_field_info(self, field_name):
        for root_type in self.__root_name_info:
            for root_name in self.__root_name_info[root_type]:
                for field in self.__root_name_info[root_type][root_name]:
                    if field["field_name"] == field_name:
                        return field

