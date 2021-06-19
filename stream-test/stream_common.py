#
# This file is part of LiteEth.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from liteeth.frontend.stream import LiteEthStream2UDPTX
from litex.soc.interconnect import stream
from liteeth.common import convert_ip


streamer_source_mac_address = 0x10e2d5000001
streamer_source_ip_address = '192.168.100.50'
streamer_target_ip_address = '192.168.100.100'
streamer_port = 1234

class Streamer(Module):
    def __init__(self, pads, target_ip: str, target_port: int, udp_port):
        self.source = stream.Endpoint([("data", pads.data.nbits)])
        self.submodules.streamer_conv = stream.Converter(pads.data.nbits, 8)
        
        # UDP Streamer
        # ------------
        payload_len = ((1500 - 42) // (pads.data.nbits // 8)) * 8
        udp_streamer   = LiteEthStream2UDPTX(
            ip_address = convert_ip(target_ip),
            udp_port   = target_port,
            fifo_depth = payload_len,
            send_level = payload_len,
        )
        self.submodules.udp_cdc      = stream.ClockDomainCrossing([("data", 8)], "sys", "eth_tx")
        self.submodules.udp_streamer = ClockDomainsRenamer("eth_tx")(udp_streamer)

        # DMA -> UDP Pipeline
        # -------------------
        self.submodules += stream.Pipeline(
            self,
            self.streamer_conv,
            self.udp_cdc,
            self.udp_streamer,
            udp_port
        )

        toggle = Signal()
        counter_preload = 2**8-1 - 243
        # counter = Signal(max=counter_preload + 1, reset=counter_preload)
        streamer_counter = Signal(max=counter_preload + 1, reset=counter_preload)

        self.comb += toggle.eq(streamer_counter == 0)
        self.comb += pads.valid.eq(toggle)
        self.sync += \
        If(toggle,
            streamer_counter.eq(counter_preload)
        ).Else(
            streamer_counter.eq(streamer_counter - 1)
        )

        self.sync += pads.data.eq(pads.data + 1)
        # self.comb += pads.data.eq(0x55)

        self.comb += self.source.valid.eq(pads.valid)
        self.comb += self.source.data.eq(pads.data)
