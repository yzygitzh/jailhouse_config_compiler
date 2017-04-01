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
            return "%ss" % length, length
        elif "u8" in c_type:
            return "B" * length, length
        elif "u16" in c_type:
            return "H" * (length / 2), length / 2
        elif "u32" in c_type:
            return "I" * (length / 4), length / 4
        elif "u64" in c_type:
            return "Q" * (length / 8), length / 8
        else:
            print "Not a basic type: %s/%s" % (c_type, length)

    def __extract_field_val(self, field_val, array_length): # accept basic type list
        if isinstance(field_val, list):
            # macro substitution
            ret_array = [self.__c_util.get_macro_val(x)
                         if self.__c_util.is_a_macro(x) else x
                         for x in field_val]
            if array_length == 1: # OR operation
                return [sum(ret_array)]
            else: # array initialization
                return ret_array + [0] * (array_length - len(ret_array))
        else:
            # macro substitution
            if self.__c_util.is_a_macro(field_val):
                return [self.__c_util.get_macro_val(field_val)]
            elif isinstance(field_val, str):
                return [field_val]
            else: # array initialization (without [] in YAML)
                return [field_val] + [0] * (array_length - 1)

    def pack_struct(self, struct_name, yaml_struct, pre_defined_vals):
        ret_bytes = ""
        struct_info = self.__c_util.get_struct_info(struct_name)
        struct_field_bytes = {}

        for field in struct_info:
            field_key = field["field_name"].split(".")[1]
            # get size tag
            size_tag, array_length = self.__infer_size_tag(field["type_info"], field["sizeof"])
            if field["field_name"] in pre_defined_vals:
                ret_bytes += struct.pack("=%s" % size_tag, pre_defined_vals[field["field_name"]])
            elif field_key in yaml_struct:
                ret_bytes += struct.pack("=%s" % size_tag,
                                         *self.__extract_field_val(yaml_struct[field_key],
                                                                   array_length))
            elif field_key in struct_field_bytes:
                ret_bytes += struct_field_bytes[field_key]
            else:
                ret_bytes += struct.pack("=%s" % size_tag, *([0] * array_length))

        return ret_bytes
