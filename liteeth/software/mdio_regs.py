#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from abc import ABC
import enum
from typing import Final

import attr

from litex.tools.utils.bitfield import *

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

class MDIORegs(metaclass=RegsListMeta):
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
        extended_capability = BitField(0, 1)

    class PHY_SPECIFIC_STATUS_COPPER(BitFieldUnion):
        addr: Final[int] = 0x11
        speed = BitField(14, 2)
        duplex = BitField(13, 1)
        page_rxed = BitField(12, 1)
        speed_and_duplex_resolved = BitField(11, 1)
        link_real_time = BitField(10, 1)
        cable_length_gige = BitField(7, 3)
        mdi_crossover = BitField(6, 1)
        downshift = BitField(5, 1)
        copper_energy_detect = BitField(4, 1)
        tx_pause_en = BitField(3, 1)
        rx_pause_en = BitField(2, 1)
        polarity_real_time = BitField(1, 1)
        jabber_real_time = BitField(0, 1)

    class EXT_PHY_SPECIFIC_CTRL(BitFieldUnion):
        addr: Final[int] = 0x14
        block_carrier_ext = BitField(15, 1)
        line_loopback = BitField(14, 1)
        disable_link_pulses = BitField(12, 1)
        downshift_counter = BitField(9, 3)
        downshift_en = BitField(8, 1)
        rgmii_rx_timing_ctrl = BitField(7, 1)
        default_mac_speed = BitField(4, 3)
        dte_detect_en = BitField(2, 1)
        rgmii_tx_timing_ctrl = BitField(1, 1)

    class RX_ERROR_COUNTER(BitFieldUnion):
        addr: Final[int] = 0x15
        rx_err_cnt = BitField(0, 16)

    class GLOBAL_STATUS(BitFieldUnion):
        addr: Final[int] = 0x17
        port_irq = BitField(0, 1)

    class EXT_PHY_SPECIFIC_STATUS(BitFieldUnion):
        addr: Final[int] = 0x1b
        fiber_copper_autosel_dis = BitField(15, 1)
        fiper_copper_resolution = BitField(13, 1)
        serial_if_autoneg_bypass_en = BitField(12, 1)
        serial_if_autoneg_bypass_status = BitField(11, 1)
        irq_polarity = BitField(10, 1)
        dis_en_auto_medium_reg_sel = BitField(9, 1)
        dte_det_status_drop_hys = BitField(5, 4)
        dte_pwr_status = BitField(4, 1)
        hw_config = BitField(0, 4)
