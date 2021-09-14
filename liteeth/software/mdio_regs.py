from abc import ABC
import enum
from typing import Final

import attr

from bitfield import *

class RegsListMeta(type):
    @classmethod
    def __prepare__(metacls, name: str, bases: tuple):
        r = collections.OrderedDict()
        return r

    def __init__(self, name: str, bases: tuple, dct: dict):
        type.__init__(self, name, bases, dct)
        for k, v in dct.items():
            if isinstance(v, BitFieldUnionMeta):
                self.addr2reg[v.addr] = v

class Regs(metaclass=RegsListMeta):
    addr2reg: Final[dict[int, BitFieldUnionMeta]] = {}

    class CONTROL_COPPER(BitFieldUnion):
        addr: Final[int] = 0x00
        reset = BitField(15, 1)
        loopback = BitField(14, 1)
        speed_sel0 = BitField(13, 1)
        autoneg_en = BitField(12, 1)
        power_down = BitField(11, 1)
        isolate = BitField(10, 1)
        restart_copper_autoneg = BitField(9, 1)
        copper_duplex_mode = BitField(8, 1)
        col_test = BitField(7, 1)
        speed_sel1 = BitField(6, 1)

    class STATUS_COPPER(BitFieldUnion):
        addr: Final[int] = 0x01
        b100base_t4 = BitField(15, 1)
        b100_x_fd = BitField(14, 1)
        b100_x_hd = BitField(13, 1)
        b10_fd = BitField(12, 1)
        b10_hd = BitField(11, 1)
        b100_t2_fd = BitField(10, 1)
        b100_t2_hd = BitField(9, 1)
        extended_status = BitField(8, 1)
        mf_preamble_suppression = BitField(6, 1)
        copper_autoneg_done = BitField(5, 1)
        copper_remote_fault = BitField(4, 1)
        autoneg_ability = BitField(3, 1)
        copper_link_status = BitField(2, 1)
        jabber_detect = BitField(1, 1)
        extended_capability = BitField(0, 0)

