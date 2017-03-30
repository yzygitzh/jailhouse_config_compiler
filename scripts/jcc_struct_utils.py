#coding=utf-8

"""Struct Related Jailhouse Config Compiler Utils
"""

import struct
import jcc_c_utils

class JCC_StructUtils():
    def __init__(self, c_util):
        self.__c_util = c_util

    def __infer_size_tag(self, c_type, length):
        if "char" in c_type:
            return "%ss" % length
        elif "u8" in c_type and length == 1:
            return "B"
        elif "u16" in c_type and length == 2:
            return "H"
        elif "u32" in c_type and length == 4:
            return "I"
        elif "u64" in c_type and length == 8:
            return "Q"
        else:
            print "Not a basic type: %s/%s" % (c_type, length)

    def pack_struct(self, struct_name, yaml_struct, pre_defined_vals):
        ret_bytes = ""
        for field in yaml_struct:
            field_key = next(iter(field.items()))[0]
            field_val = next(iter(field.items()))[1]
            field_path = ".".join([struct_name, field_key])
            field_info = self.__c_util.get_field_info(field_path)
            if self.__c_util.is_a_struct(field_key) or \
               self.__c_util.is_a_union(field_key):
                ret_bytes += self.pack_struct(field_key, field_val, pre_defined_vals)
            else:
                # get size tag
                size_tag = self.__infer_size_tag(field_info["type_info"], field_info["sizeof"])
                print field_path, size_tag
                if self.__c_util.is_a_macro(field_val):
                    field_val = self.__c_util.get_macro_val(field_val)
                ret_bytes += struct.pack("=%s" % size_tag, field_val)
        return ret_bytes
