#
# This file is part of LiteEth.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from migen import *

from liteeth.frontend.stream import LiteEthStream2UDPTX
from litex.soc.interconnect import stream
from liteeth.common import convert_ip


streamer_source_mac_address = 0x10e2d5000001
streamer_source_ip_address = '192.168.100.50'
streamer_target_ip_address = '192.168.100.100'
streamer_port = 1234
# streamer_max_packet_size = 1500 - 42 # too much, overflows sometimes and i dunno why
streamer_max_packet_size = 1024


class TickerZeroToMax(Module):
    def __init__(self, pads: Record, max_cnt: int):
        self.counter = counter = Signal(max=max_cnt)
        self.tick = tick = Signal()
        print(pads)
        assert counter.nbits <= pads.counter.nbits

        self.comb += pads.tick.eq(tick)
        self.comb += pads.counter.eq(counter)
        self.sync += \
            If(counter == max_cnt,
               tick.eq(1),
               counter.eq(0)
            ).Else(
                tick.eq(0),
                counter.eq(counter + 1)
            )

    @classmethod
    def from_period(cls, pads: Record, sys_clk_freq: int, ticker_period: float) -> TickerZeroToMax:
        counter_preload = int(sys_clk_freq * ticker_period) - 1
        return cls(pads, counter_preload)

    @classmethod
    def from_freq(cls, pads: Record, sys_clk_freq: int, ticker_freq: int) -> TickerZeroToMax:
        return cls.from_period(pads, sys_clk_freq, 1 / ticker_freq)


class BeatTickerZeroToMax(Module):
    def __init__(self, pads: Record, max_cnt_a: int, max_cnt_b: int):
        self.tick = tick = Signal()

        pads_a = Record([
            ("tick", pads.tick_a),
            ("counter", pads.counter_a),
        ], "ticker_a")
        self.submodules.ticker_a = TickerZeroToMax(pads_a, max_cnt_a)

        pads_b = Record([
            ("tick", pads.tick_b),
            ("counter", pads.counter_b),
        ], "ticker_b")
        self.submodules.ticker_b = TickerZeroToMax(pads_b, max_cnt_b)

        self.comb += pads.tick.eq(tick)
        self.comb += tick.eq(self.ticker_a.tick & self.ticker_b.tick)

    @classmethod
    def from_period(cls, pads: Record, sys_clk_freq: int, ticker_period_a: float, ticker_period_b: float) -> BeatTickerZeroToMax:
        counter_preload_a = int(sys_clk_freq * ticker_period_a) - 1
        counter_preload_b = int(sys_clk_freq * ticker_period_b) - 1
        return cls(pads, max_cnt_a=counter_preload_a, max_cnt_b=counter_preload_b)

    @classmethod
    def from_freq(cls, pads: Record, sys_clk_freq: int, ticker_freq_a: int, ticker_freq_b: int) -> BeatTickerZeroToMax:
        return cls.from_period(pads, sys_clk_freq, 1 / ticker_freq_a, 1 / ticker_freq_b)


class PipelineSource(Module):
    def __init__(self, pads: Record, ticker: TickerZeroToMax, beat_ticker: BeatTickerZeroToMax):
        self.source_tick = tick = Signal()
        self.source_counter = counter = Signal(64)
        self.submodules.ticker = ticker
        self.submodules.beat_ticker = beat_ticker

        self.valid = valid = Signal()
        self.source = stream.Endpoint([("data", counter.nbits)])
        self.submodules.sink_fifo = stream.SyncFIFO(layout=self.source.payload.layout, depth=4)
        self.submodules.stream_conv = stream.Converter(counter.nbits, 8)

        self.submodules.pipeline = stream.Pipeline(
            self,
            self.stream_conv,
            self.sink_fifo,
        )

        # self.comb += tick.eq(self.ticker.tick & ~self.beat_ticker.tick)
        # self.comb += pads.source_tick.eq(tick)
        # self.comb += pads.source_counter.eq(counter)

        self.comb += tick.eq(self.ticker.tick)
        self.comb += pads.source_tick.eq(tick)
        self.comb += pads.source_counter.eq(counter)
        self.comb += pads.source_valid.eq(valid)
        self.comb += pads.sink_valid.eq(self.sink_fifo.source.valid)
        self.comb += pads.sink_ready.eq(self.sink_fifo.source.ready)
        self.comb += pads.sink_first.eq(self.sink_fifo.source.first)
        self.comb += pads.sink_last.eq(self.sink_fifo.source.last)
        self.comb += pads.sink_payload.eq(self.sink_fifo.source.payload.raw_bits())
        self.comb += self.source.valid.eq(valid)
        self.comb += self.source.data.eq(counter)
        self.comb += self.sink_fifo.source.ready.eq(1)
        self.comb += valid.eq(1)

        self.sync += \
            If(tick,
               counter.eq(counter + 1),
            )



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
        counter_preload = int(sys_clk_freq * period / 2)
        # counter_preload = 2**16-1
        counter_preload = 127
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
