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

from __future__ import absolute_import, division, print_function

import typing
from builtins import *

import canmatrix
import logging
import canmatrix.log

logger = logging.getLogger(__name__)


def get_frame_info(db, frame):
    # type: (canmatrix.CanMatrix, canmatrix.Frame) -> typing.List[str]
    ret_array = []  # type: typing.List[str]
    # frame-id

    ret_array.append("%sh" % frame.slot_id)
    # frame-Name
    ret_array.append(frame.name)

    ret_array.append(frame.effective_cycle_time)

    # determine send-type
    if "GenMsgSendType" in db.frame_defines:
        ret_array.append(frame.attribute("GenMsgSendType", db=db))
        if "GenMsgDelayTime" in db.frame_defines:
            ret_array.append(frame.attribute("GenMsgDelayTime", db=db))
        else:
            ret_array.append("")
    else:
        ret_array.append("")
        ret_array.append("")
    return ret_array


def get_pdu_info(db, pdu):
    ret_array = []  # type: typing.List[str]
    # export pdu related info,'PDU_Name', 'PDU_Type', 'PDU_Length','PDU_PortType',

    if pdu.name is not None:
        ret_array.append(pdu.name)
    else:
        ret_array.append("")
    if pdu.pdu_type is not None:
        ret_array.append(pdu.pdu_type)
    else:
        ret_array.append("")
    if pdu.size is not None:
        ret_array.append(pdu.size)
    else:
        ret_array.append("")
    if pdu.port_type is not None:
        ret_array.append(pdu.port_type)
    else:
        ret_array.append("")

    logger.debug("pdu info in get_pdu_info is :"+str(ret_array))
    return ret_array


def get_signal(db, sig, motorola_bit_format):
    # type: (canmatrix.CanMatrix, canmatrix.Signal, str) -> typing.Tuple[typing.List, typing.List]
    front_array = []  # type: typing.List[typing.Union[str, float]]
    back_array = []
    if motorola_bit_format == "msb":
        start_bit = sig.get_startbit(bit_numbering=1)
    elif motorola_bit_format == "msbreverse":
        start_bit = sig.get_startbit()
    else:  # motorolaBitFormat == "lsb"
        start_bit = sig.get_startbit(bit_numbering=1, start_little=True)

    # start byte
    front_array.append(int(start_bit / 8) + 1)
    # start bit
    front_array.append(start_bit % 8)
    # signal name
    front_array.append(sig.system_signal_name)

    # eval comment:
    comment = sig.comment if sig.comment else ""

    # eval multiplex-info
    if sig.multiplex == 'Multiplexor':
        comment = "Mode Signal: " + comment
    elif sig.multiplex is not None:
        comment = "Mode " + str(sig.multiplex) + ":" + comment

    # write comment and size of signal in sheet
    front_array.append(comment)
    front_array.append(sig.size)

    # start-value of signal available
    front_array.append(sig.initial_value)

    # SNA-value of signal available
    if "GenSigSNA" in db.signal_defines:
        sna = sig.attribute("GenSigSNA", db=db)
        if sna is not None:
            sna = sna[1:-1]
        front_array.append(sna)
    # no SNA-value of signal available / just for correct style:
    else:
        front_array.append(" ")

    # eval byteorder (little_endian: intel == True / motorola == 0)
    if sig.is_little_endian:
        front_array.append("i")
    else:
        front_array.append("m")

    # is a unit defined for signal?
    if sig.unit.strip():
        # factor not 1.0 ?
        if float(sig.factor) != 1:
            back_array.append("%g" % float(sig.factor) + "  " + sig.unit)
        # factor == 1.0
        else:
            back_array.append(sig.unit)
    # no unit defined
    else:
        # factor not 1.0 ?
        if float(sig.factor) != 1:
            back_array.append("%g -" % float(sig.factor))
        # factor == 1.0
        else:
            back_array.append("")
    '''        
    if sig.pdu_name is not None:
        back_array.append(sig.pdu_name.strip())
        logger.debug("signal related PDU name is :"+sig.pdu_name.strip())
    if sig.pdu_type is not None:
        back_array.append(sig.pdu_type.strip())
    if sig.pdu_length is not None:
        back_array.append(sig.pdu_length)
    if sig.pdu_portType is not None:
        back_array.append(sig.pdu_portType.strip())
    '''
    if sig.signal_group is not None:
        back_array.append(str(sig.signal_group))
        logger.debug("signal related signal_group is :"+str(sig.signal_group))
    return front_array, back_array
