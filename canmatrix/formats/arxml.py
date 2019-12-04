# -*- coding: utf-8 -*-
# Copyright (c) 2013, Eduard Broecker
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that
# the following conditions are met:
#
#    Redistributions of source code must retain the above copyright notice, this list of conditions and the
#    following disclaimer.
#    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#    following disclaimer in the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

#
# this script exports arxml-files from a canmatrix-object
# arxml-files are the can-matrix-definitions and a lot more in AUTOSAR-Context
# currently Support for Autosar 3.2 and 4.0-4.3 is planned

from __future__ import absolute_import, division, print_function

import decimal
import logging
import typing
from builtins import *

import lxml.etree

import canmatrix
import canmatrix.types
import canmatrix.utils

logger = logging.getLogger(__name__)
default_float_factory = decimal.Decimal

clusterExporter = 1
clusterImporter = 1


class ArTree(object):
    def __init__(self, name="", ref=None):  # type: (str, lxml.etree._Element) -> None
        self._name = name
        self._ref = ref
        self._array = []  # type: typing.List[ArTree]

    def append_child(self, name, child):  # type: (str, typing.Any) -> ArTree
        """Append new child and return it."""
        temp = ArTree(name, child)
        self._array.append(temp)
        return temp

    def get_child_by_name(self, name):  # type: (str) -> typing.Union[ArTree, None]
        for child in self._array:
            if child._name == name:
                return child
        return None

    @property
    def ref(self):  # type: () -> lxml.etree._Element
        return self._ref


# for typing only
_Element = lxml.etree._Element
_DocRoot = typing.Union[_Element, ArTree]
_MultiplexId = typing.Union[str, int, None]
_FloatFactory = typing.Callable[[typing.Any], typing.Any]


def create_sub_element(parent, element_name, text=None):
    # type: (_Element, str, typing.Optional[str]) -> _Element
    sn = lxml.etree.SubElement(parent, element_name)
    if text is not None:
        sn.text = str(text)
    return sn


def get_base_type_of_signal(signal):
    # type: (canmatrix.Signal) -> typing.Tuple[str, int]
    """Get signal arxml-type and size based on the Signal properties."""
    if signal.is_float:
        if signal.size > 32:
            create_type = "double"
            size = 64
        else:
            create_type = "single"
            size = 32
    else:
        if signal.size > 32:
            if signal.is_signed:
                create_type = "sint64"
            else:
                create_type = "uint64"
            size = 64                            
        elif signal.size > 16:
            if signal.is_signed:
                create_type = "sint32"
            else:
                create_type = "uint32"
            size = 32                            
        elif signal.size > 8:
            if signal.is_signed:
                create_type = "sint16"
            else:
                create_type = "uint16"
            size = 16
        else:
            if signal.is_signed:
                create_type = "sint8"
            else:
                create_type = "uint8"
            size = 8
    return create_type, size


###################################
# read ARXML
###################################

def fill_tree_from_xml(tag, ar_tree, namespace):
    # type: (_Element, ArTree, str) -> None
    """Parse the xml tree into ArTree objects."""
    for child in tag:  # type: _Element
        name_elem = child.find('./' + namespace + 'SHORT-NAME')
        # long_name = child.find('./' + namespace + 'LONG-NAME')
        if name_elem is not None and child is not None:
            fill_tree_from_xml(child, ar_tree.append_child(name_elem.text, child), namespace)
        if name_elem is None and child is not None:
            fill_tree_from_xml(child, ar_tree, namespace)


def find_children_by_path(from_element, path, root_or_cache, namespace):
    # type: (_Element, str, _DocRoot, str) -> typing.Sequence[_Element]
    path_elements = path.split('/')
    element = from_element
    for element_name in path_elements[:-1]:
        element = get_child(element, element_name, root_or_cache, namespace)
    children = get_children(element, path_elements[-1], root_or_cache, namespace)
    return children


def ar_path_to_x_path(ar_path, dest_element=None):
    # type: (str, typing.Optional[str]) -> str
    """Get path in translation-dictionary."""
    ar_path_elements = ar_path.strip('/').split('/')
    xpath = "."

    for element in ar_path_elements[:-1]:
        xpath += "//A:SHORT-NAME[text()='" + element + "']/.."
    if dest_element:
        xpath += "//A:" + dest_element + "/A:SHORT-NAME[text()='" + ar_path_elements[-1] + "']/.."
    else:
        xpath += "//A:SHORT-NAME[text()='" + ar_path_elements[-1] + "']/.."

    return xpath


xml_element_cache = dict()  # type: typing.Dict[str, _Element]


def get_element_by_path(tree, path_and_name, namespace):
    # type: (_Element, str, str) -> typing.Union[_Element, None]
    """Find sub-element of given path with given short name."""
    global xml_element_cache
    namespace_map = {'A': namespace[1:-1]}
    base_path, element_name = path_and_name.rsplit('/', 1)
    if base_path in xml_element_cache:
        base_element = xml_element_cache[base_path]
    else:
        base_xpath = ar_path_to_x_path(base_path)
        elems = tree.xpath(base_xpath, namespaces=namespace_map)
        base_element = elems[0] if elems else None
        xml_element_cache[base_path] = base_element

    element_found = None
    if base_element is not None:
        element_found = base_element.xpath(
            ".//A:SHORT-NAME[text()='{name}']/..".format(name=element_name),
            namespaces=namespace_map)[0]
    return element_found


def get_cached_element_by_path(data_tree, path):
    # type: (ArTree, str) -> typing.Optional[_Element]
    """Get element from ArTree by path."""
    if not isinstance(data_tree, ArTree):
        logger.warning("%s not called with ArTree, return None", get_cached_element_by_path.__name__)
        return None
    ptr = data_tree
    for name in path.split('/'):
        if ptr is None:
            return None
        if name.strip():
            ptr = ptr.get_child_by_name(name)
    return ptr.ref if ptr else None


def get_child(parent, tag_name, root_or_cache, namespace):
    # type: (_Element, str, _DocRoot, str) -> typing.Optional[_Element]
    """Get first sub-child or referenced sub-child with given name."""
    # logger.debug("get_child: " + tag_name)
    if parent is None:
        return None
    ret = parent.find('.//' + namespace + tag_name)
    if ret is None:  # no direct element - try reference
        reference = parent.find('.//' + namespace + tag_name + '-REF')
        if reference is not None:
            if isinstance(root_or_cache, ArTree):
                ret = get_cached_element_by_path(root_or_cache, reference.text)
            else:
                ret = get_element_by_path(root_or_cache, reference.text, namespace)
    return ret


def get_children(parent, tag_name, root_or_cache, namespace):
    # type: (_Element, str, _DocRoot, str) -> typing.Sequence[_Element]
    if parent is None:
        return []
    ret = parent.findall('.//' + namespace + tag_name)
    if not ret:  # no direct element - get references
        ret_list = parent.findall('.//' + namespace + tag_name + '-REF')
        if isinstance(root_or_cache, ArTree):
            ret = [get_cached_element_by_path(root_or_cache, item.text) for item in ret_list]
        else:
            ret = [get_element_by_path(root_or_cache, item.text, namespace) for item in ret_list]
    return ret


def get_element_name(parent, ns):
    # type: (_Element, str) -> str
    """Get element short name."""
    name = parent.find('./' + ns + 'SHORT-NAME')
    if name is not None and name.text is not None:
        return name.text
    return ""


pdu_frame_mapping = {}  # type: typing.Dict[_Element, str]
signal_rxs = {}  # type: typing.Dict[_Element, canmatrix.Signal]


def get_sys_signals(sys_signal, sys_signal_array, frame, group_id, ns):
    # type: (_Element, typing.Sequence[_Element], canmatrix.Frame, int, str) -> None
    members = [get_element_name(signal, ns) for signal in sys_signal_array]
    '''new added for check the signal in signal group whether in the pdu or frame'''
    for signal in sys_signal_array:
        frame.add_signal(signal)
    group_name = get_element_name(sys_signal, ns)
    logger.debug("01 in get_sys_signals function, signal group name:"+group_name+", group_id: "+str(group_id)+", signal name list: "+str(members))
    
    frame.add_signal_group(group_name, group_id, members)  # todo use group_id instead of 1?
    '''for the flexray, input frame is set as the PDU name '''

    if frame.get_signal_group_for_signal(sys_signal_array[0]) is None:
        logger.debug("02 in get_sys_signals function,signal group not found with signal "+get_element_name(sys_signal_array[0],ns))
    else:
        logger.debug("03 in get_sys_signals function,signal group "+frame.get_signal_group_for_signal(sys_signal_array[0])+" found by signal "+get_element_name(sys_signal_array[0],ns))



def decode_compu_method(compu_method, root_or_cache, ns, float_factory):
    # type: (_Element, _DocRoot, str, _FloatFactory) -> typing.Tuple
    values = {}
    factor = float_factory(1.0)
    offset = float_factory(0)
    unit = get_child(compu_method, "UNIT", root_or_cache, ns)
    const = None
    compu_scales = find_children_by_path(compu_method, "COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE", root_or_cache, ns)
    for compu_scale in compu_scales:
        ll = get_child(compu_scale, "LOWER-LIMIT", root_or_cache, ns)
        ul = get_child(compu_scale, "UPPER-LIMIT", root_or_cache, ns)
        sl = get_child(compu_scale, "SHORT-LABEL", root_or_cache, ns)
        if sl is None:
            desc = get_element_desc(compu_scale, root_or_cache, ns)
        else:
            desc = sl.text
        #####################################################################################################
        # Modification to support sourcing the COMPU_METHOD info from the Vector NETWORK-REPRESENTATION-PROPS
        # keyword definition. 06Jun16
        #####################################################################################################
        if ll is not None and desc is not None and int(float_factory(ul.text)) == int(float_factory(ll.text)):
            #####################################################################################################
            #####################################################################################################
            values[ll.text] = desc

        scale_desc = get_element_desc(compu_scale, root_or_cache, ns)
        rational = get_child(compu_scale, "COMPU-RATIONAL-COEFFS", root_or_cache, ns)
        if rational is not None:
            numerator_parent = get_child(rational, "COMPU-NUMERATOR", root_or_cache, ns)
            numerator = get_children(numerator_parent, "V", root_or_cache, ns)
            denominator_parent = get_child(rational, "COMPU-DENOMINATOR", root_or_cache, ns)
            denominator = get_children(denominator_parent, "V", root_or_cache, ns)
            try:
                factor = float_factory(numerator[1].text) / float_factory(denominator[0].text)
                offset = float_factory(numerator[0].text) / float_factory(denominator[0].text)
            except decimal.DivisionByZero:
                if numerator[0].text != denominator[0].text or numerator[1].text != denominator[1].text:
                    logger.warning("ARXML signal scaling: polynom is not supported and it is replaced by factor=1 and offset =0.")
                factor = float_factory(1)
                offset = float_factory(0)
        else:
            const = get_child(compu_scale, "COMPU-CONST", root_or_cache, ns)
            # add value
            if const is None:
                logger.warning("Unknown Compu-Method: at sourceline %d ", compu_method.sourceline)
    return values, factor, offset, unit, const


def eval_type_of_signal(type_encoding, base_type, ns):
    if type_encoding == "NONE":
        is_signed = False
        is_float = False
    elif type_encoding == "2C":
        is_signed = True
        is_float = False
    elif type_encoding == "IEEE754" or type_encoding == "SINGLE" or type_encoding == "DOUBLE":
        is_signed = True
        is_float = True
    elif type_encoding == "BOOLEAN":
        is_signed = False
        is_float = False
    elif base_type is not None:
        is_float = False
        type_name = get_element_name(base_type, ns)
        if type_name[0] == 'u':
            is_signed = False  # unsigned
        else:
            is_signed = True  # signed
    else:
        is_float = False
        is_signed = False  # signed
    return is_signed, is_floatecu_name,


def get_signals(xml_signal_pdu_mapping_array, frame, pdu, ecu_name,root_or_cache, ns, multiplex_id, float_factory, bit_offset=0):
    # type: (typing.Sequence[_Element], canmatrix.Frame, _DocRoot, str, _MultiplexId, typing.Callable, int) -> None
    """Add signals from xml to the Frame."""
    global signal_rxs
    group_id = 1
    xml_isignals_name_in_group=list()
    if xml_signal_pdu_mapping_array is None:  # Empty signalarray - nothing to do
        return
    for xml_signal_pdu_mapping in xml_signal_pdu_mapping_array:
        #compu_method = None
        motorola = get_child(xml_signal_pdu_mapping, "PACKING-BYTE-ORDER", root_or_cache, ns)
        start_bit = get_child(xml_signal_pdu_mapping, "START-POSITION", root_or_cache, ns)

        xml_isignal = get_child(xml_signal_pdu_mapping, "I-SIGNAL", root_or_cache, ns)
        xml_isignal_group = get_child(xml_signal_pdu_mapping, "I-SIGNAL-GROUP", root_or_cache, ns)
        xml_system_signal = get_child(xml_isignal, "SYSTEM-SIGNAL", root_or_cache, ns)
        """it is possible that I-SIGNAL or I-SIGNAL-GROUP is in the PDU tag, both signal and signal mapping ref will be defined in the I-PDU."""

        if xml_isignal is None:
            logger.debug('In PDU %s, no isignal found in mapping %s,',pdu.name,get_element_name(xml_signal_pdu_mapping,ns))
        else:
            str_signal_name = get_element_name(xml_isignal,ns)
            str_system_signal_name = get_element_name(xml_system_signal,ns)
            #base_type = get_child(xml_isignal, "BASE-TYPE", root_or_cache, ns)
            #try:
                #type_encoding = get_child(base_type, "BASE-TYPE-ENCODING", root_or_cache, ns).text
            #except AttributeError:
                #type_encoding = "None"            
            length = get_child(xml_isignal, "LENGTH", root_or_cache, ns)
            #unit_element = get_child(xml_isignal, "UNIT", root_or_cache, ns)
            #unit_element = ""
            is_little_endian = False
            if motorola is not None:
                if motorola.text == 'MOST-SIGNIFICANT-BYTE-LAST':
                    is_little_endian = True
            else:
                logger.debug('no name byte order for signal' + str_signal_name)
            signal_description = get_element_desc(xml_system_signal, root_or_cache, ns)

            if start_bit is None:
                start_bit.text = 0
            struct_signal = canmatrix.Signal(
                str_signal_name,
                start_bit=int(start_bit.text) + bit_offset,
                size=int(length.text),
                is_little_endian=is_little_endian,
                comment=signal_description,
                system_signal_name = str_system_signal_name)

        # save signal, to determin receiver-ECUs for this signal later
        signal_rxs[xml_system_signal] = struct_signal
        if ecu_name is not None:
            signal_rxs[xml_system_signal].add_receiver(ecu_name)            
        
        if xml_isignal_group is not None:
            isignal_in_signal_group_array = get_children(xml_isignal_group, "I-SIGNAL", root_or_cache, ns)
            xml_system_signal_group = get_child(xml_isignal_group, "SYSTEM-SIGNAL-GROUP", root_or_cache, ns)
            group_name = get_element_name(xml_system_signal_group,ns)
            
            for temp in isignal_in_signal_group_array:
                signal_name_in_group = get_element_name(temp,ns)
                xml_isignals_name_in_group.append(signal_name_in_group)
            group_id = group_id + 1            
            pdu.add_signal_group(group_name,group_id,xml_isignals_name_in_group)
            frame.add_signal_group(group_name,group_id,xml_isignals_name_in_group)
            logger.debug(" get_sys_signals called in get_signals: signal found in I-SIGNAL-GROUP "+str(get_element_name(xml_isignal_group, ns))+" for signal list: "+str(xml_isignals_name_in_group))
            struct_signal.signal_group = str(get_element_name(xml_isignal_group, ns))
            continue

        frame.add_signal(struct_signal)
        pdu.add_signal(struct_signal)


def get_frame_from_multiplexed_ipdu(pdu, target_frame, multiplex_translation, root_or_cache, ns, float_factory):
    selector_byte_order = get_child(pdu, "SELECTOR-FIELD-BYTE-ORDER", root_or_cache, ns)
    selector_len = get_child(pdu, "SELECTOR-FIELD-LENGTH", root_or_cache, ns)
    selector_start = get_child(pdu, "SELECTOR-FIELD-START-POSITION", root_or_cache, ns)
    is_little_endian = False
    if selector_byte_order.text == 'MOST-SIGNIFICANT-BYTE-LAST':
        is_little_endian = True
    is_signed = False  # unsigned
    multiplexor = canmatrix.Signal(
        "Multiplexor",
        start_bit=int(selector_start.text),
        size=int(selector_len.text),
        is_little_endian=is_little_endian,
        multiplex="Multiplexor")

    multiplexor.initial_value = 0
    target_frame.add_signal(multiplexor)
    static_part = get_child(pdu, "STATIC-PART", root_or_cache, ns)
    ipdu = get_child(static_part, "I-PDU", root_or_cache, ns)
    if ipdu is not None:
        pdu_sig_mappings = get_child(ipdu, "SIGNAL-TO-PDU-MAPPINGS", root_or_cache, ns)
        pdu_sig_mapping = get_children(pdu_sig_mappings, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
        get_signals(pdu_sig_mapping, target_frame, root_or_cache, ns, None, float_factory)
        multiplex_translation[get_element_name(ipdu, ns)] = get_element_name(pdu, ns)

    dynamic_part = get_child(pdu, "DYNAMIC-PART", root_or_cache, ns)
    #               segmentPositions = arGetChild(dynamic_part, "SEGMENT-POSITIONS", arDict, ns)
    #               segmentPosition = arGetChild(segmentPositions, "SEGMENT-POSITION", arDict, ns)
    #               byteOrder = arGetChild(segmentPosition, "SEGMENT-BYTE-ORDER", arDict, ns)
    #               segLength = arGetChild(segmentPosition, "SEGMENT-LENGTH", arDict, ns)
    #               segPos = arGetChild(segmentPosition, "SEGMENT-POSITION", arDict, ns)
    dynamic_part_alternatives = get_child(dynamic_part, "DYNAMIC-PART-ALTERNATIVES", root_or_cache, ns)
    dynamic_part_alternative_list = get_children(dynamic_part_alternatives, "DYNAMIC-PART-ALTERNATIVE",
                                                 root_or_cache, ns)
    for alternative in dynamic_part_alternative_list:
        selector_id = get_child(alternative, "SELECTOR-FIELD-CODE", root_or_cache, ns)
        ipdu = get_child(alternative, "I-PDU", root_or_cache, ns)
        multiplex_translation[get_element_name(ipdu, ns)] = get_element_name(pdu, ns)
        if ipdu is not None:
            pdu_sig_mappings = get_child(ipdu, "SIGNAL-TO-PDU-MAPPINGS", root_or_cache, ns)
            pdu_sig_mapping = get_children(pdu_sig_mappings, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
            get_signals(pdu_sig_mapping, target_frame, root_or_cache, ns, selector_id.text, float_factory)


def get_frame_from_container_ipdu(pdu, target_frame, root_or_cache, ns, float_factory):
    target_frame.is_fd = True
    pdus = get_children(pdu, "CONTAINED-PDU-TRIGGERING", root_or_cache, ns)
    signal_group_id = 1
    singnals_grouped = []  # type: typing.List[str]
    header_type = get_child(pdu, "HEADER-TYPE", root_or_cache, ns).text
    if header_type == "SHORT-HEADER":
        header_length = 32
        target_frame.add_signal(canmatrix.Signal(start_bit=0, size=24, name="Header_ID", multiplex="Multiplexor", is_little_endian=True))
        target_frame.add_signal(canmatrix.Signal(start_bit=24, size=8, name="Header_DLC", is_little_endian=True))
    elif header_type == "LONG-HEADER":
        header_length = 64
        target_frame.add_signal(canmatrix.Signal(start_bit=0, size=32, name="Header_ID", multiplex="Multiplexor",
                                                 is_little_endian=True))
        target_frame.add_signal(canmatrix.Signal(start_bit=32, size=32, name="Header_DLC", is_little_endian=True))
    else:
        raise("header " + header_type + " not supported for containers yet")
        # none type
        # TODO

    for cpdu in pdus:
        ipdu = get_child(cpdu, "I-PDU", root_or_cache, ns)
        try:
            if header_type == "SHORT-HEADER":
                header_id = get_child(ipdu, "HEADER-ID-SHORT-HEADER", root_or_cache, ns).text
            elif header_type == "LONG-HEADER":
                header_id = get_child(ipdu, "HEADER-ID-LONG-HEADER", root_or_cache, ns).text
            else:
                # none type
                pass
        except AttributeError:
            header_id = "0"
        if header_id.startswith("0x"):
            header_id = int(header_id, 16)
        else:
            header_id = int(header_id)

        # pdu_sig_mapping = get_children(ipdu, "I-SIGNAL-IN-I-PDU", root_or_cache, ns)
        pdu_sig_mapping = get_children(ipdu, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
        # TODO
        if pdu_sig_mapping:
            get_signals(pdu_sig_mapping, target_frame, root_or_cache, ns, header_id, float_factory, bit_offset=header_length)
            new_signals = []
            for signal in target_frame:
                if signal.name not in singnals_grouped and signal.name is not "Header_ID" and signal.name is not "Header_DLC":
                    new_signals.append(signal.name)
            target_frame.add_signal_group("HEARDER_ID_" + str(header_id), signal_group_id, new_signals)
            singnals_grouped += new_signals
            signal_group_id += 1


def store_frame_timings(target_frame, cyclic_timing, event_timing, minimum_delay, repeats, starting_time, time_offset, repeating_time, root_or_cache, time_period, ns, float_factory):
    if cyclic_timing is not None and event_timing is not None:
        target_frame.add_attribute("GenMsgSendType", "cyclicAndSpontanX")  # CycleAndSpontan
        if minimum_delay is not None:
            target_frame.add_attribute("GenMsgDelayTime", str(int(float_factory(minimum_delay.text) * 1000)))
        if repeats is not None:
            target_frame.add_attribute("GenMsgNrOfRepetitions", repeats.text)
    elif cyclic_timing is not None:
        target_frame.add_attribute("GenMsgSendType", "cyclicX")  # CycleX
        if minimum_delay is not None:
            target_frame.add_attribute("GenMsgDelayTime", str(int(float_factory(minimum_delay.text) * 1000)))
        if repeats is not None:
            target_frame.add_attribute("GenMsgNrOfRepetitions", repeats.text)
    else:
        target_frame.add_attribute("GenMsgSendType", "spontanX")  # Spontan
        if minimum_delay is not None:
            target_frame.add_attribute("GenMsgDelayTime", str(int(float_factory(minimum_delay.text) * 1000)))
        if repeats is not None:
            target_frame.add_attribute("GenMsgNrOfRepetitions", repeats.text)

    if starting_time is not None:
        value = get_child(starting_time, "VALUE", root_or_cache, ns)
        target_frame.add_attribute("GenMsgStartDelayTime", str(int(float_factory(value.text) * 1000)))
    elif cyclic_timing is not None:
        value = get_child(time_offset, "VALUE", root_or_cache, ns)
        if value is not None:
            target_frame.add_attribute("GenMsgStartDelayTime", str(int(float_factory(value.text) * 1000)))

    value = get_child(repeating_time, "VALUE", root_or_cache, ns)
    if value is not None:
        target_frame.cycle_time = int(float_factory(value.text) * 1000)
    elif cyclic_timing is not None:
        value = get_child(time_period, "VALUE", root_or_cache, ns)
        if value is not None:
            target_frame.cycle_time = int(float_factory(value.text) * 1000)


def get_frame(frame_triggering, root_or_cache, multiplex_translation, ns, float_factory):
    # type: (_Element, _DocRoot, dict, str, typing.Callable) -> typing.Union[canmatrix.Frame, None]
    global pdu_frame_mapping
    address_mode = get_child(frame_triggering, "CAN-ADDRESSING-MODE", root_or_cache, ns)
    frame_rx_behaviour_elem = get_child(frame_triggering, "CAN-FRAME-RX-BEHAVIOR", root_or_cache, ns)
    frame_tx_behaviour_elem = get_child(frame_triggering, "CAN-FRAME-TX-BEHAVIOR", root_or_cache, ns)
    is_fd_elem = get_child(frame_triggering, "CAN-FD-FRAME-SUPPORT", root_or_cache, ns)

    arb_id = get_child(frame_triggering, "IDENTIFIER", root_or_cache, ns)
    frame_elem = get_child(frame_triggering, "FRAME", root_or_cache, ns)

    frame_name_elem = get_child(frame_triggering, "SHORT-NAME", root_or_cache, ns)
    logger.debug("processing Frame: %s", frame_name_elem.text)
    if arb_id is None:
        logger.info("found Frame %s without arbitration id", frame_name_elem.text)
        return None
    arbitration_id = int(arb_id.text)

    if frame_elem is not None:
        dlc_elem = get_child(frame_elem, "FRAME-LENGTH", root_or_cache, ns)
        pdu_mappings = get_child(frame_elem, "PDU-TO-FRAME-MAPPINGS", root_or_cache, ns)
        pdu_mapping = get_child(pdu_mappings, "PDU-TO-FRAME-MAPPING", root_or_cache, ns)
        pdu = get_child(pdu_mapping, "PDU", root_or_cache, ns)  # SIGNAL-I-PDU

        if pdu is not None and 'SECURED-I-PDU' in pdu.tag:
            payload = get_child(pdu, "PAYLOAD", root_or_cache, ns)
            pdu = get_child(payload, "I-PDU", root_or_cache, ns)
            # logger.info("found secured pdu - no signal extraction possible: %s", get_element_name(pdu, ns))

        pdu_frame_mapping[pdu] = get_element_name(frame_elem, ns)

        new_frame = canmatrix.Frame(get_element_name(frame_elem, ns), size=int(dlc_elem.text))
        comment = get_element_desc(frame_elem, root_or_cache, ns)
        if comment is not None:
            new_frame.add_comment(comment)
    else:
        # without frameinfo take short-name of frametriggering and dlc = 8
        logger.debug("Frame %s has no FRAME-REF", frame_name_elem.text)
        ipdu_triggering_refs = get_child(frame_triggering, "I-PDU-TRIGGERING-REFS", root_or_cache, ns)
        ipdu_triggering = get_child(ipdu_triggering_refs, "I-PDU-TRIGGERING", root_or_cache, ns)
        pdu = get_child(ipdu_triggering, "I-PDU", root_or_cache, ns)
        if pdu is None:
            pdu = get_child(ipdu_triggering, "I-SIGNAL-I-PDU", root_or_cache, ns)  # AR4.2
        dlc_elem = get_child(pdu, "LENGTH", root_or_cache, ns)
        new_frame = canmatrix.Frame(frame_name_elem.text, arbitration_id=arbitration_id, size=int(int(dlc_elem.text) / 8))

    if pdu is None:
        logger.error("pdu is None")
    else:
        logger.debug(get_element_name(pdu, ns))

    if pdu is not None and "MULTIPLEXED-I-PDU" in pdu.tag:
        get_frame_from_multiplexed_ipdu(pdu, new_frame, multiplex_translation, root_or_cache, ns, float_factory)

    if new_frame.comment is None:
        new_frame.add_comment(get_element_desc(pdu, root_or_cache, ns))

    if address_mode is not None and address_mode.text == 'EXTENDED':
        new_frame.arbitration_id = canmatrix.ArbitrationId(arbitration_id, extended=True)
    else:
        new_frame.arbitration_id = canmatrix.ArbitrationId(arbitration_id, extended=False)

    if (frame_rx_behaviour_elem is not None and frame_rx_behaviour_elem.text == 'CAN-FD') or \
        (frame_tx_behaviour_elem is not None and frame_tx_behaviour_elem.text == 'CAN-FD') or \
        (is_fd_elem is not None and is_fd_elem.text == 'TRUE'):
        new_frame.is_fd = True
    else:
        new_frame.is_fd = False

    timing_spec = get_child(pdu, "I-PDU-TIMING-SPECIFICATION", root_or_cache, ns)
    if timing_spec is None:
        timing_spec = get_child(pdu, "I-PDU-TIMING-SPECIFICATIONS", root_or_cache, ns)
    cyclic_timing = get_child(timing_spec, "CYCLIC-TIMING", root_or_cache, ns)
    repeating_time = get_child(cyclic_timing, "REPEATING-TIME", root_or_cache, ns)

    event_timing = get_child(timing_spec, "EVENT-CONTROLLED-TIMING", root_or_cache, ns)
    repeats = get_child(event_timing, "NUMBER-OF-REPEATS", root_or_cache, ns)
    minimum_delay = get_child(timing_spec, "MINIMUM-DELAY", root_or_cache, ns)
    starting_time = get_child(timing_spec, "STARTING-TIME", root_or_cache, ns)

    time_offset = get_child(cyclic_timing, "TIME-OFFSET", root_or_cache, ns)
    time_period = get_child(cyclic_timing, "TIME-PERIOD", root_or_cache, ns)

    store_frame_timings(new_frame, cyclic_timing, event_timing, minimum_delay, repeats, starting_time, time_offset, repeating_time, root_or_cache, time_period, ns, float_factory)

    if pdu.tag == ns + "CONTAINER-I-PDU":
        get_frame_from_container_ipdu(pdu, new_frame, root_or_cache, ns, float_factory)

    else:
        pdu_sig_mapping = get_children(pdu, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
        if pdu_sig_mapping:
            get_signals(pdu_sig_mapping, new_frame, root_or_cache, ns, None, float_factory)
        # Seen some pdu_sig_mapping being [] and not None with some arxml 4.2
        else:  # AR 4.2
            pdu_trigs = get_children(frame_triggering, "PDU-TRIGGERINGS", root_or_cache, ns)
            if pdu_trigs is not None:
                for pdu_trig in pdu_trigs:
                    trig_ref_cond = get_child(pdu_trig, "PDU-TRIGGERING-REF-CONDITIONAL", root_or_cache, ns)
                    trigs = get_child(trig_ref_cond, "PDU-TRIGGERING", root_or_cache, ns)
                    ipdus = get_child(trigs, "I-PDU", root_or_cache, ns)

                    signal_to_pdu_maps = get_child(ipdus, "I-SIGNAL-TO-PDU-MAPPINGS", root_or_cache, ns)
                    if signal_to_pdu_maps is None:
                        signal_to_pdu_maps = get_child(ipdus, "I-SIGNAL-TO-I-PDU-MAPPINGS", root_or_cache, ns)

                    if signal_to_pdu_maps is None:
                        logger.debug("AR4.x PDU %s no SIGNAL-TO-PDU-MAPPINGS found - no signal extraction!",
                                     get_element_name(ipdus, ns))
                    # signal_to_pdu_map = get_children(signal_to_pdu_maps, "I-SIGNAL-TO-I-PDU-MAPPING", arDict, ns)
                    get_signals(signal_to_pdu_maps, new_frame, root_or_cache, ns, None, float_factory)  # todo BUG expects list, not item
            else:
                logger.debug("Frame %s (assuming AR4.2) no PDU-TRIGGERINGS found", new_frame.name)
    new_frame.fit_dlc()
    return new_frame


def get_element_desc(element, ar_tree, ns):
    # type: (_Element, _DocRoot, str) -> str
    """Get element description from XML."""
    desc = get_child(element, "DESC", ar_tree, ns)
    txt = get_child(desc, 'L-2[@L="DE"]', ar_tree, ns)
    if txt is None:
        txt = get_child(desc, 'L-2[@L="EN"]', ar_tree, ns)
    if txt is None:
        txt = get_child(desc, 'L-2', ar_tree, ns)
    if txt is not None:
        return txt.text
    else:
        return ""


def process_ecu(ecu_elem, db, ar_dict, multiplex_translation, ns):
    # type: (_Element, canmatrix.CanMatrix, _DocRoot, typing.Mapping[str, str], str) -> canmatrix.Ecu
    global pdu_frame_mapping
    connectors = get_child(ecu_elem, "CONNECTORS", ar_dict, ns)
    diag_address = get_child(ecu_elem, "DIAGNOSTIC-ADDRESS", ar_dict, ns)
    diag_response = get_child(ecu_elem, "RESPONSE-ADDRESSS", ar_dict, ns)
    # TODO: use diag_address for frame-classification
    comm_connector = get_child(connectors, "COMMUNICATION-CONNECTOR", ar_dict, ns)
    if comm_connector is None:
        comm_connector = get_child(connectors, "CAN-COMMUNICATION-CONNECTOR", ar_dict, ns)
    frames = find_children_by_path(comm_connector, "ECU-COMM-PORT-INSTANCES/FRAME-PORT", ar_dict, ns)
    nm_address = get_child(comm_connector, "NM-ADDRESS", ar_dict, ns)
    assoc_refs = get_child(ecu_elem, "ASSOCIATED-I-PDU-GROUP-REFS", ar_dict, ns)

    if assoc_refs is not None:
        assoc = get_children(assoc_refs, "ASSOCIATED-I-PDU-GROUP", ar_dict, ns)
    else:  # AR4
        assoc_refs = get_child(ecu_elem, "ASSOCIATED-COM-I-PDU-GROUP-REFS", ar_dict, ns)
        assoc = get_children(assoc_refs, "ASSOCIATED-COM-I-PDU-GROUP", ar_dict, ns)

    in_frame = []
    out_frame = []

    # get direction of frames (is current ECU sender/receiver/...?)
    for ref in assoc:
        direction = get_child(ref, "COMMUNICATION-DIRECTION", ar_dict, ns)
        group_refs = get_child(ref, "CONTAINED-I-PDU-GROUPS-REFS", ar_dict, ns)
        pdu_refs = get_child(ref, "I-PDU-REFS", ar_dict, ns)
        if pdu_refs is not None:  # AR3
            # local defined pdus
            pdus = get_children(pdu_refs, "I-PDU", ar_dict, ns)
            for pdu in pdus:
                if pdu in pdu_frame_mapping:
                    if direction.text == "IN":
                        in_frame.append(pdu_frame_mapping[pdu])
                    else:
                        out_frame.append(pdu_frame_mapping[pdu])
        else:  # AR4
            isigpdus = get_child(ref, "I-SIGNAL-I-PDUS", ar_dict, ns)
            isigconds = get_children(
                isigpdus, "I-SIGNAL-I-PDU-REF-CONDITIONAL", ar_dict, ns)
            for isigcond in isigconds:
                pdus = get_children(isigcond, "I-SIGNAL-I-PDU", ar_dict, ns)
                for pdu in pdus:
                    if pdu in pdu_frame_mapping:
                        if direction.text == "IN":
                            in_frame.append(pdu_frame_mapping[pdu])
                        else:
                            out_frame.append(pdu_frame_mapping[pdu])

        # grouped pdus
        group = get_children(group_refs, "CONTAINED-I-PDU-GROUPS", ar_dict, ns)
        for t in group:
            if direction is None:
                direction = get_child(
                    t, "COMMUNICATION-DIRECTION", ar_dict, ns)
            pdu_refs = get_child(t, "I-PDU-REFS", ar_dict, ns)
            pdus = get_children(pdu_refs, "I-PDU", ar_dict, ns)
            for pdu in pdus:
                if direction.text == "IN":
                    in_frame.append(get_element_name(pdu, ns))
                else:
                    out_frame.append(get_element_name(pdu, ns))

        for out in out_frame:
            if out in multiplex_translation:
                out = multiplex_translation[out]
            frame = db.frame_by_name(out)
            if frame is not None:
                frame.add_transmitter(get_element_name(ecu_elem, ns))
            else:
                pass

#               for inf in inFrame:
#                       if inf in multiplexTranslation:
#                               inf = multiplexTranslation[inf]
#                       frame = db.frameByName(inf)
#                       if frame is not None:
#                               for signal in frame.signals:
#                                       recname = arGetName(ecu, ns)
#                                       if recname not in  signal.receiver:
#                                               signal.receiver.append(recname)
#                       else:
#                               print "in not found: " + inf
    new_ecu = canmatrix.Ecu(get_element_name(ecu_elem, ns))
    if nm_address is not None:
        new_ecu.add_attribute("NWM-Stationsadresse", nm_address.text)
        new_ecu.add_attribute("NWM-Knoten", "ja")
    else:
        new_ecu.add_attribute("NWM-Stationsadresse", "0")
        new_ecu.add_attribute("NWM-Knoten", "nein")
    return new_ecu


def ecuc_extract_signal(signal_node, ns):
    # type: (_Element, str) -> canmatrix.Signal
    """Extract signal from ECUc file."""
    attributes = signal_node.findall(".//" + ns + "DEFINITION-REF")  # type: typing.Sequence[_Element]
    start_bit = None
    size = 0
    is_little = False
    # endianness = None
    # init_value = 0
    # signal_type = None
    # timeout = 0
    for attribute in attributes:
        if attribute.text.endswith("ComBitPosition"):
            start_bit = int(attribute.getparent().find(".//" + ns + "VALUE").text)
        if attribute.text.endswith("ComBitSize"):
            size = int(attribute.getparent().find(".//" + ns + "VALUE").text)
        if attribute.text.endswith("ComSignalEndianness"):
            endianness = attribute.getparent().find(".//" + ns + "VALUE").text
            is_little = "LITTLE_ENDIAN" in endianness
        if attribute.text.endswith("ComSignalInitValue"):
            init_value = int(attribute.getparent().find(".//" + ns + "VALUE").text)
        if attribute.text.endswith("ComSignalType"):
            signal_type = attribute.getparent().find(".//" + ns + "VALUE").text
        if attribute.text.endswith("ComTimeout"):
            timeout = int(attribute.getparent().find(".//" + ns + "VALUE").text)
    return canmatrix.Signal(get_element_name(signal_node, ns), start_bit=start_bit, size=size, is_little_endian=is_little)


def extract_cm_from_ecuc(com_module, root_or_cache, ns):
    # type: (_Element, _DocRoot, str) -> typing.Dict[str, canmatrix.CanMatrix]
    db = canmatrix.CanMatrix()
    definitions = com_module.findall('.//' + ns + "DEFINITION-REF")
    for definition in definitions:
        if definition.text.endswith("ComIPdu"):
            container = definition.getparent()
            frame = canmatrix.Frame(get_element_name(container, ns))
            db.add_frame(frame)
            all_references = get_children(container, "ECUC-REFERENCE-VALUE", root_or_cache, ns)
            for reference in all_references:
                value = get_child(reference, "VALUE", root_or_cache, ns)
                if value is not None:
                    signal_definition = value.find('./' + ns + "DEFINITION-REF")
                    if signal_definition.text.endswith("ComSignal"):
                        signal = ecuc_extract_signal(value, ns)
                        frame.add_signal(signal)
    db.recalc_dlc(strategy="max")
    return {"": db}

def decode_ethernet_helper(root, root_or_cache, ns, float_factory):
    found_matrixes = {}
    ecs = root.findall('.//' + ns + 'ETHERNET-CLUSTER')
    for ec in ecs:
        baudrate_elem = ec.find(".//" + ns + "BAUDRATE")
        physical_channels = ec.findall('.//' + ns + "ETHERNET-PHYSICAL-CHANNEL")
        for pc in physical_channels:
            db = canmatrix.CanMatrix()
            db.baudrate = baudrate_elem.text if baudrate_elem is not None else 0
            db.add_signal_defines("LongName", 'STRING')
            channel_name = get_element_name(pc, ns)
            found_matrixes[channel_name] = db
            ipdu_triggerings = pc.findall('.//' + ns + "PDU-TRIGGERING")

            #network_endpoints = pc.findall('.//' + ns + "NETWORK-ENDPOINT")
            for ipdu_triggering in ipdu_triggerings:
                ipdu = get_child(ipdu_triggering, "I-PDU", root_or_cache, ns)
                ipdu_name = get_element_name(ipdu, ns)
                target_frame = canmatrix.Frame(name = ipdu_name)
                pdu_sig_mapping = get_children(ipdu, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
                get_signals(pdu_sig_mapping, target_frame, root_or_cache, ns, None, float_factory)
                db.add_frame(target_frame)
    return found_matrixes

def decode_flexray_helper(root, root_or_cache, ns, float_factory):
    found_matrixes = {}
    logger.debug("-------------decode_flexray_helper is excuted------------.")
    fcs = root.findall('.//' + ns + 'FLEXRAY-CLUSTER')
    frame_counter = 0
    for fc in fcs:
        physical_channels = fc.findall('.//' + ns + "FLEXRAY-PHYSICAL-CHANNEL")
        for pc in physical_channels:
            db = canmatrix.CanMatrix()
            db.is_flexray = True
            db.add_ecu_defines("NWM-Stationsadresse", 'HEX 0 63')
            db.add_ecu_defines("NWM-Knoten", 'ENUM  "nein","ja"')        
            db.add_signal_defines("LongName", 'STRING')
            db.add_frame_defines("GenMsgDelayTime", 'INT 0 65535')
            db.add_frame_defines("GenMsgNrOfRepetitions", 'INT 0 65535')
            db.add_frame_defines("GenMsgStartValue", 'STRING')
            db.add_frame_defines("GenMsgStartDelayTime", 'INT 0 65535')
            db.add_frame_defines("GenMsgSendType",
                                 'ENUM  "cyclicX","spontanX","cyclicIfActiveX","spontanWithDelay","cyclicAndSpontanX","cyclicAndSpontanWithDelay","spontanWithRepitition","cyclicIfActiveAndSpontanWD","cyclicIfActiveFast","cyclicWithRepeatOnDemand","none"')

            channel_name = get_element_name(pc, ns)
            found_matrixes[channel_name] = db
            frame_triggers = pc.findall('.//' + ns + "FLEXRAY-FRAME-TRIGGERING")
            for xml_frame_trigger in frame_triggers:
                frame_counter += 1
                logger.debug(" flexray_helper frame_counter is :"+str(frame_counter))
                frame_name = get_element_name(xml_frame_trigger, ns)
                slot_id = int(get_child(xml_frame_trigger, "SLOT-ID", root_or_cache, ns).text)
                base_cycle = get_child(xml_frame_trigger, "BASE-CYCLE", root_or_cache, ns).text
                ipdu_triggerings = get_children(xml_frame_trigger, "PDU-TRIGGERING", root_or_cache, ns)
                frame_repetition_cycle = find_children_by_path(xml_frame_trigger, "CYCLE-REPETITION/CYCLE-REPETITION", root_or_cache, ns)[0].text
                network_endpoints = pc.findall('.//' + ns + "NETWORK-ENDPOINT")
                frame_size = int(find_children_by_path(xml_frame_trigger, "FRAME/FRAME-LENGTH", root_or_cache, ns)[0].text)
                # for flexray,create the new frame struct object.
                struct_frame = canmatrix.Frame(size = frame_size, arbitration_id = frame_counter)
                struct_frame.name = frame_name
                struct_frame.is_FlexrayFrame = True
                struct_frame.slot_id = str(slot_id)+"-"+str(base_cycle)+"-"+frame_repetition_cycle.split("-")[-1]
                struct_frame.arbitration_id = canmatrix.ArbitrationId(frame_counter, extended=False)
                struct_frame.base_cycle = base_cycle
                struct_frame.repitition_cycle = frame_repetition_cycle.replace("CYCLE-REPETITION-","")
                struct_frame.cycle_time = 5*int(struct_frame.repitition_cycle)
                frame_counter += 1
                logger.debug("flexray_helper frame name is :"+str(frame_name))
                #db.add_frame(frame)
                logger.debug(" flexray_helper slot_id is :"+str(slot_id))
                logger.debug(" flexray_helper base_cycle is :"+str(base_cycle))
                logger.debug(" flexray_helper frame_repetition_cycle is :"+str(struct_frame.repitition_cycle))
                logger.debug(" flexray_helper frame_size is :"+str(frame_size))
                for ipdu_triggering in ipdu_triggerings:
                    if ipdu_triggering is None:
                        logger.debug(" flexray_helper ipdu_triggering is none.")
                    else:
                        logger.debug(" flexray_helper ipdu_triggering name is :"+str(get_element_name(ipdu_triggering, ns)))
                    ipdu_triggering_name = get_element_name(ipdu_triggering, ns)
                    '''there are 3 type pdu, N-PDU, NM-PDU,I-SIGNAL-I-PDU. '''
                    pdu_type = ipdu_triggering.find('.//'+ns+"I-PDU-REF").attrib["DEST"]
                    if pdu_type.find("I-PDU") !=-1:
                        struct_frame.add_attribute("GenMsgSendType", "cyclicX")
                    else:
                        struct_frame.add_attribute("GenMsgSendType", "spontanX")
                    ipdu = get_child(ipdu_triggering, "I-PDU", root_or_cache, ns)
                    ipdu_name = get_element_name(ipdu, ns)
                    
                    ipdu_length = int(ipdu.find('.//'+ns+"LENGTH").text)
                    pdu_port = get_child(ipdu_triggering, "I-PDU-PORT-REF", root_or_cache, ns)
                    pdu_port_type = get_child(ipdu_triggering, "I-PDU-PORT-REF", root_or_cache, ns).text.split("/")[-1]
                    recieve_ecu_name = None
                    if pdu_port_type.find("IN"):
                        recieve_ecu_name = get_element_name(pdu_port.getparent().getparent().getparent().getparent(), ns)                    
                    #logger.debug(" flexray_helper pdu_type is :"+str(pdu_type))
                    #logger.debug(" flexray_helper ipdu_length is :"+str(ipdu_length))
                    #logger.debug(" flexray_helper pdu_port_type is :"+str(pdu_port_type))
                    #logger.debug(" flexray_helper ipdu_name is :"+str(ipdu_name))
                    target_pdu = canmatrix.Pdu(name = ipdu_name, size=ipdu_length,pdu_type=pdu_type,
                                               triggering_name = ipdu_triggering_name, port_type=pdu_port_type)
                    
                    sig_pdu_mappings = get_children(ipdu, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
                    
                    if sig_pdu_mappings is None or len(sig_pdu_mappings)==0:
                        logger.debug(" flexray_helper no I-SIGNAL-TO-I-PDU-MAPPING found under PDU:"+str(ipdu_name))
                    else:
                        get_signals(sig_pdu_mappings, struct_frame,target_pdu, recieve_ecu_name,root_or_cache, ns, None, float_factory)   
                    
                    isignal_in_sig_pdu_mappings = get_children(ipdu, "I-SIGNAL", root_or_cache, ns) 
                    for struct_signal in  target_pdu.signals:
                        struct_signal.pdu_name = ipdu_name
                        struct_signal.pdu_type = pdu_type
                        struct_signal.pdu_length = ipdu_length
                        struct_signal.pdu_portType = pdu_port_type
                        sig_group = target_pdu.get_signal_group_for_signal(str(struct_signal))
                        if sig_group is not None:
                            struct_signal.signal_group = str(sig_group.name)
                    for isignal in  isignal_in_sig_pdu_mappings:
                        isignal_name = get_element_name(isignal, ns)
                        #logger.debug(" flexray_helper found signal under PDU is :"+str(isignal_name))                  
                    struct_frame.add_pdu(target_pdu)
                db.add_frame(struct_frame)
    return found_matrixes

def decode_can_helper(root, root_or_cache, ns, float_factory, ignore_cluster_info):
    found_matrixes = {}
    logger.debug("-------------decode_can_helper is excuted------------.")
    ccs = root.findall('.//' + ns + 'CAN-CLUSTER')
    frame_counter = 0
    for cc in ccs:
        speed = get_child(cc, "SPEED", root_or_cache, ns)
        physical_channels = cc.findall('.//' + ns + "CAN-PHYSICAL-CHANNEL")
        for pc in physical_channels:
            db = canmatrix.CanMatrix()
            db.is_flexray = False
            db.add_ecu_defines("NWM-Stationsadresse", 'HEX 0 63')
            db.add_ecu_defines("NWM-Knoten", 'ENUM  "nein","ja"')            
            db.add_signal_defines("LongName", 'STRING')
            db.add_frame_defines("GenMsgDelayTime", 'INT 0 65535')
            db.add_frame_defines("GenMsgNrOfRepetitions", 'INT 0 65535')
            db.add_frame_defines("GenMsgStartValue", 'STRING')
            db.add_frame_defines("GenMsgStartDelayTime", 'INT 0 65535')
            db.add_frame_defines("GenMsgSendType",
                                 'ENUM  "cyclicX","spontanX","cyclicIfActiveX","spontanWithDelay","cyclicAndSpontanX","cyclicAndSpontanWithDelay","spontanWithRepitition","cyclicIfActiveAndSpontanWD","cyclicIfActiveFast","cyclicWithRepeatOnDemand","none"')

            channel_name = get_element_name(cc, ns)
            found_matrixes[channel_name] = db
            frame_triggers = pc.findall('.//' + ns + "CAN-FRAME-TRIGGERING")
            for xml_frame_trigger in frame_triggers:
                frame_counter += 1
                logger.debug(" flexray_helper frame_counter is :"+str(frame_counter))
                frame_name = get_element_name(xml_frame_trigger, ns)
                arb_id = get_child(xml_frame_trigger, "IDENTIFIER", root_or_cache, ns)
                arbitration_id = int(arb_id.text)
                
                ipdu_triggerings = get_children(xml_frame_trigger, "PDU-TRIGGERING", root_or_cache, ns)
                
                network_endpoints = pc.findall('.//' + ns + "NETWORK-ENDPOINT")
                frame_size = int(find_children_by_path(xml_frame_trigger, "FRAME/FRAME-LENGTH", root_or_cache, ns)[0].text)
                # for flexray,create the new frame struct object.
                struct_frame = canmatrix.Frame(size = frame_size, arbitration_id = frame_counter)
                struct_frame.name = frame_name
                struct_frame.is_FlexrayFrame = False

                struct_frame.arbitration_id = canmatrix.ArbitrationId(arbitration_id, extended=False)
                struct_frame.slot_id = str(hex(arbitration_id))
                '''net frame cycle time info is in the I-PDU , so it will be set in the i-pdu process part.'''
                #struct_frame.cycle_time 
                logger.debug(" can_helper frame name is :"+str(frame_name))
                #db.add_frame(frame)
                logger.debug(" can_helper frame_size is :"+str(frame_size))
                for ipdu_triggering in ipdu_triggerings:
                    if ipdu_triggering is None:
                        logger.debug(" can_helper ipdu_triggering is none.")
                    else:
                        logger.debug(" can_helper ipdu_triggering name is :"+str(get_element_name(ipdu_triggering, ns)))
                    ipdu_triggering_name = get_element_name(ipdu_triggering, ns)
                    '''there are 3 type pdu, N-PDU, NM-PDU,I-SIGNAL-I-PDU. '''
                    pdu_type = ipdu_triggering.find('.//'+ns+"I-PDU-REF").attrib["DEST"]
                    if pdu_type.find("I-PDU") !=-1:
                        struct_frame.add_attribute("GenMsgSendType", "cyclicX")
                    else:
                        struct_frame.add_attribute("GenMsgSendType", "spontanX")
                    ipdu = get_child(ipdu_triggering, "I-PDU", root_or_cache, ns)
                    ipdu_name = get_element_name(ipdu, ns)
                    timing_spec = get_child(ipdu, "I-PDU-TIMING-SPECIFICATIONS", root_or_cache, ns)
                    cyclic_timing = get_child(timing_spec, "CYCLIC-TIMING", root_or_cache, ns)
                    time_period = get_child(cyclic_timing, "TIME-PERIOD", root_or_cache, ns)
                    value = get_child(time_period, "VALUE", root_or_cache, ns)
                    if value is not None:
                        #pdu_cycle_time_xml_path = "I-PDU-TIMING-SPECIFICATIONS/I-PDU-TIMING/TRANSMISSION-MODE-DECLARATION/TRANSMISSION-MODE-TRUE-TIMING/CYCLIC-TIMING/TIME-PERIOD/VALUE"
                        #pdu_cycle_time = ipdu.find('.//'+ns+pdu_cycle_time_xml_path)            
                        struct_frame.cycle_time = int(float_factory(value.text)*1000)
                    ipdu_length = int(ipdu.find('.//'+ns+"LENGTH").text)
                    pdu_port = get_child(ipdu_triggering, "I-PDU-PORT-REF", root_or_cache, ns)
                    pdu_port_type = get_child(ipdu_triggering, "I-PDU-PORT-REF", root_or_cache, ns).text.split("/")[-1]
                    recieve_ecu_name = None
                    if pdu_port_type.find("IN"):
                        recieve_ecu_name = get_element_name(pdu_port.getparent().getparent().getparent().getparent(), ns)                    
                    #logger.debug(" can_helper pdu_type is :"+str(pdu_type))
                    #logger.debug(" can_helper ipdu_length is :"+str(ipdu_length))
                    #logger.debug(" can_helper pdu_port_type is :"+str(pdu_port_type))
                    #logger.debug(" can_helper ipdu_name is :"+str(ipdu_name))
                    target_pdu = canmatrix.Pdu(name = ipdu_name, size=ipdu_length,pdu_type=pdu_type,
                                               triggering_name = ipdu_triggering_name, port_type=pdu_port_type)
                    
                    sig_pdu_mappings = get_children(ipdu, "I-SIGNAL-TO-I-PDU-MAPPING", root_or_cache, ns)
                    
                    if sig_pdu_mappings is None or len(sig_pdu_mappings)==0:
                        logger.debug(" can_helper no I-SIGNAL-TO-I-PDU-MAPPING found under PDU:"+str(ipdu_name))
                    else:
                        get_signals(sig_pdu_mappings, struct_frame,target_pdu, recieve_ecu_name,root_or_cache, ns, None, float_factory)   
                    
                    isignal_in_sig_pdu_mappings = get_children(ipdu, "I-SIGNAL", root_or_cache, ns) 
                    for struct_signal in  target_pdu.signals:
                        struct_signal.pdu_name = ipdu_name
                        struct_signal.pdu_type = pdu_type
                        struct_signal.pdu_length = ipdu_length
                        struct_signal.pdu_portType = pdu_port_type
                        sig_group = target_pdu.get_signal_group_for_signal(str(struct_signal))
                        if sig_group is not None:
                            struct_signal.signal_group = str(sig_group.name)
                    for isignal in  isignal_in_sig_pdu_mappings:
                        isignal_name = get_element_name(isignal, ns)
                        #logger.debug(" can_helper found signal under PDU is :"+str(isignal_name))                  
                    struct_frame.add_pdu(target_pdu)
                db.add_frame(struct_frame)
    return found_matrixes

def load(file, **options):
    # type: (typing.IO, **typing.Any) -> typing.Dict[str, canmatrix.CanMatrix]

    global xml_element_cache
    xml_element_cache = dict()
    global pdu_frame_mapping
    pdu_frame_mapping = {}
    global signal_rxs
    signal_rxs = {}

    float_factory = options.get("float_factory", default_float_factory)  # type: typing.Callable
    ignore_cluster_info = options.get("arxmlIgnoreClusterInfo", False)
    use_ar_xpath = options.get("arxmlUseXpath", False)

    decode_ethernet = options.get("decode_ethernet", False)
    decode_flexray = options.get("decode_flexray", False)

    result = {}
    logger.debug("Read arxml ...")
    tree = lxml.etree.parse(file)

    root = tree.getroot()  # type: _Element
    logger.debug(" Done\n")

    ns = "{" + tree.xpath('namespace-uri(.)') + "}"  # type: str
    logger.debug("current ns value is : "+ns)
    nsp = tree.xpath('namespace-uri(.)')

    top_level_packages = root.find('./' + ns + 'TOP-LEVEL-PACKAGES')

    if top_level_packages is None:
        # no "TOP-LEVEL-PACKAGES found, try root
        logger.debug("no TOP-LEVEL-PACKAGES found, use tree.getroot() as top_level_packages")
        top_level_packages = root

    logger.debug("Build arTree ...")

    if use_ar_xpath:
        search_point = top_level_packages  # type: typing.Union[_Element, ArTree]
    else:
        ar_tree = ArTree()
        fill_tree_from_xml(top_level_packages, ar_tree, ns)
        search_point = ar_tree
        logger.debug("use ar_tree structure object filled by etree root as the search point.")
    logger.debug(" Done\n")

    if isinstance(search_point, ArTree):
        com_module = get_cached_element_by_path(search_point, "ActiveEcuC/Com")
        logger.debug("search_point is ArTree instance, use get_cached_element_by_path to get com_module.")
    else:
        com_module = get_element_by_path(search_point, "ActiveEcuC/Com", ns)
        logger.debug("search_point is not ArTree instance, use get_element_by_path to get com_module.")
    if com_module is not None:
        logger.info("seems to be a ECUC arxml. Very limited support for extracting canmatrix.")
        return extract_cm_from_ecuc(com_module, search_point, ns)

    result.update(decode_can_helper(root, search_point, ns, float_factory, ignore_cluster_info))

    result.update(decode_flexray_helper(root, search_point, ns, float_factory))

    if decode_ethernet:
        result.update(decode_ethernet_helper(root, search_point, ns, float_factory))

    return result
