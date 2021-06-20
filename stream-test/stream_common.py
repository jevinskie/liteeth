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
streamer_max_packet_size = 1500 - 42

class Streamer(Module):
    def __init__(self, sys_clk_freq: int, target_ip: str, target_port: int, udp_port, bitrate: int = 15_000_000, nbits: int=64):
        assert nbits % 8 == 0 and nbits > 0
        self.source = stream.Endpoint([("data", nbits)])
        self.submodules.streamer_conv = stream.Converter(nbits, 8)

        # UDP Streamer
        # ------------
        payload_len = (streamer_max_packet_size // (nbits // 8)) * 8
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
        self.submodules.pipeline = stream.Pipeline(
            self,
            self.streamer_conv,
            self.udp_cdc,
            self.udp_streamer,
            udp_port
        )

        self.valid = valid = Signal()
        self.running_counter = running_counter = Signal(nbits)
        self.toggle = toggle = Signal()
        # counter_preload = 2**8-1 - 243
        # period = 1 / (bitrate / 8 / payload_len)
        period = 1 / (bitrate / nbits)
        counter_preload = int(sys_clk_freq*period/2)
        print(f'bitrate: {bitrate} period: {period} counter_preload: {counter_preload}')
        calc_bitrate = (1 / period) * nbits
        print(f'calc_bitrate: {calc_bitrate}')
        # counter = Signal(max=counter_preload + 1, reset=counter_preload)
        self.streamer_counter = streamer_counter = Signal(max=counter_preload + 1)

        self.comb += toggle.eq(streamer_counter == 0)
        self.comb += valid.eq(1)
        self.sync += \
        If(toggle,
            streamer_counter.eq(counter_preload)
        ).Else(
            streamer_counter.eq(streamer_counter - 1)
        )

        self.sync += \
        If(self.source.ready,
            running_counter.eq(running_counter + 1)
        )

        self.comb += self.source.valid.eq(valid)
        self.comb += self.source.data.eq(running_counter)
