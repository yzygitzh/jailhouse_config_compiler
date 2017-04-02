#coding=utf-8

"""Struct Related Jailhouse Config Compiler Utils
"""

import struct
import jcc_c_utils

class JCC_StructUtils():
    def __init__(self, c_util):
        self.__c_util = c_util
        self.__pre_defined_vals = {}

    def __infer_size_tag(self, c_type, length): # accept basic c_type only
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

    def __extract_field_val(self, field_info, field_val): # accept (non)basic type field
        ret_bytes = ""
        type_info = field_info["type_info"]
        sizeof = field_info["sizeof"]
        if isinstance(field_val, list):
            # array of struct
            if self.__c_util.is_a_struct(type_info):
                return "".join([self.pack_struct(type_info, field_val) for x in field_val])
            # array of union
            if self.__c_util.is_a_union(type_info):
                return "".join([self.pack_struct(type_info, field_val) for x in field_val])
            # array of basic type
            else:
                # macro substitution
                size_tag, array_length = self.__infer_size_tag(type_info, sizeof)
                ret_array = [self.__c_util.get_macro_val(x)
                             if self.__c_util.is_a_macro(x) else x
                             for x in field_val]
                if array_length == 1: # OR operation
                    return struct.pack("=%s" % size_tag, sum(ret_array))
                else: # array initialization
                    return struct.pack("=%s" % size_tag,
                                       *(ret_array + [0] * (array_length - len(ret_array))))
        elif isinstance(field_val, dict): # single struct
            return self.pack_struct(type_info, field_val)
        else:
            # single basic type
            size_tag, array_length = self.__infer_size_tag(type_info, sizeof)
            if self.__c_util.is_a_macro(field_val):
                return struct.pack("=%s" % size_tag, self.__c_util.get_macro_val(field_val))
            elif isinstance(field_val, str):
                return struct.pack("=%s" % size_tag, field_val)
            else: # array initialization (without [] in YAML)
                return struct.pack("=%s" % size_tag, *([field_val] + [0] * (array_length - 1)))

    def pack_struct(self, struct_name, yaml_struct):
        ret_bytes = ""
        struct_info = self.__c_util.get_struct_info(struct_name)

        for field in struct_info:
            print field["field_name"]
            field_key = field["field_name"].split(".")[-1]
            # expand pre_defined vals; TODO: now basic non-array type only
            if field["field_name"] in self.__pre_defined_vals:
                size_tag, _ = self.__infer_size_tag(field["type_info"], field["sizeof"])
                ret_bytes += struct.pack("=%s" % size_tag, self.__pre_defined_vals[field["field_name"]])
            elif field_key in yaml_struct:
                ret_bytes += self.__extract_field_val(field, yaml_struct[field_key])
            else: # field not found; fill sizeof "0" bytes
                ret_bytes += struct.pack("=" + "B" * field["sizeof"], *([0] * field["sizeof"]))

        return ret_bytes

    def add_pre_defined_vals(self, key, val):
        self.__pre_defined_vals[key] = val