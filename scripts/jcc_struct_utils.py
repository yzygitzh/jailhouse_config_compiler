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

    def __extract_field_val(self, field_val):
        if isinstance(field_val, list):
            return sum([self.__c_util.get_macro_val(x)
                        if self.__c_util.is_a_macro(x) else x
                        for x in field_val])
        else:
            if self.__c_util.is_a_macro(field_val):
                return self.__c_util.get_macro_val(field_val)
            else:
                return field_val

    def pack_struct(self, struct_name, yaml_struct, pre_defined_vals):
        ret_bytes = ""
        struct_info = self.__c_util.get_struct_info(struct_name)
        yaml_fields = {}

        for field in yaml_struct:
            field_key = next(iter(field.items()))[0]
            field_val = next(iter(field.items()))[1]
            if self.__c_util.is_a_struct(field_key) or \
               self.__c_util.is_a_union(field_key):
                ret_bytes += self.pack_struct(field_key, field_val, pre_defined_vals)
            else:
                yaml_fields[field_key] = self.__extract_field_val(field_val)

        for field in struct_info:
            field_key = field["field_name"].split(".")[1]
            # get size tag
            size_tag = self.__infer_size_tag(field["type_info"], field["sizeof"])
            if field["field_name"] in pre_defined_vals:
                ret_bytes += struct.pack("=%s" % size_tag, pre_defined_vals[field["field_name"]])
            elif field_key in yaml_fields:
                ret_bytes += struct.pack("=%s" % size_tag, yaml_fields[field_key])
            else:
                ret_bytes += struct.pack("=%s" % size_tag, 0)

        return ret_bytes
