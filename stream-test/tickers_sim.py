#!/usr/bin/env python3

#
# This file is part of LiteEth.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse

from migen import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from stream_common import *

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("sys_clk", 0, Pins(1)),
    ("sys_rst", 0, Pins(1)),
    ("ticker_zero_to_max", 0,
        Subsignal("tick", Pins(1)),
        Subsignal("counter", Pins(32)),
    ),
    ("ticker_zero_to_max_from_freq", 0,
        Subsignal("tick", Pins(1)),
        Subsignal("counter", Pins(32)),
    ),
    ("beat_ticker", 0,
        Subsignal("tick", Pins(1)),
        Subsignal("tick_a", Pins(1)),
        Subsignal("counter_a", Pins(32)),
        Subsignal("tick_b", Pins(1)),
        Subsignal("counter_b", Pins(32)),
     ),
    ("stream_out", 0,
        Subsignal("source_tick", Pins(1)),
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_counter", Pins(64)),
        Subsignal("sink_valid", Pins(1)),
        Subsignal("sink_ready", Pins(1)),
        Subsignal("sink_first", Pins(1)),
        Subsignal("sink_last", Pins(1)),
        Subsignal("sink_payload", Pins(8)),
     )
    # ("beat_ticker", 0,
    #  Subsignal("tick", Pins(1)),
    #  Subsignal("ticker_a", Pins(1)),
    #  Subsignal("counter_a", Pins(32)),
    #  Subsignal("tick_b", Pins(1)),
    #  Subsignal("counter_b", Pins(32)),
    #  ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(SimPlatform):
    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

# Bench SoC ----------------------------------------------------------------------------------------

class BenchSoC(SoCCore):
    def __init__(self, sim_debug=False, trace_reset_on=False, **kwargs):
        platform     = Platform()
        sys_clk_freq = int(1e6)

        # SoCMini ----------------------------------------------------------------------------------
        SoCMini.__init__(self, platform, clk_freq=sys_clk_freq,
            ident          = "LiteEth stream Simulation",
            ident_version  = True
        )

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request("sys_clk"))

        # Ticker -----------------------------------------------------------------------------------
        ticker_zero_to_max = TickerZeroToMax(self.platform.request("ticker_zero_to_max"), max_cnt=15)
        # self.submodules.ticker_zero_to_max_from_freq = TickerZeroToMax.from_freq(self.platform.request("ticker_zero_to_max_from_freq"), sys_clk_freq=sys_clk_freq, ticker_freq=sys_clk_freq/16)
        bt_pads = self.platform.request("beat_ticker")
        beat_ticker = BeatTickerZeroToMax(bt_pads, max_cnt_a=5, max_cnt_b=7)
        # beat_ticker = None

        # Pipeline ---------------------------------------------------------------------------------
        self.submodules.stream = PipelineSource(self.platform.request("stream_out"), ticker_zero_to_max, beat_ticker)

        if sim_debug:
            platform.add_debug(self, reset=1 if trace_reset_on else 0)
        else:
            self.comb += platform.trace.eq(1)

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteEth Stream Simulation")
    parser.add_argument("--trace",                action="store_true",     help="Enable Tracing")
    parser.add_argument("--trace-fst",            action="store_true",     help="Enable FST tracing (default=VCD)")
    parser.add_argument("--trace-start",          default="0",             help="Time to start tracing (ps)")
    parser.add_argument("--trace-end",            default="-1",            help="Time to end tracing (ps)")
    parser.add_argument("--trace-exit",           action="store_true",     help="End simulation once trace finishes")
    parser.add_argument("--sim-end",              default="-1",            help="Time to end simulation (ps)")
    parser.add_argument("--sim-debug",            action="store_true",     help="Add simulation debugging modules")
    args = parser.parse_args()
    try:
        args.trace_start = int(args.trace_start)
    except:
        args.trace_start = int(float(args.trace_start))
    try:
        args.trace_end = int(args.trace_end)
    except:
        args.trace_end = int(float(args.trace_end))

    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=1e6)

    soc     = BenchSoC(sim_debug=args.sim_debug, trace_reset_on=args.trace_start > 0 or args.trace_end > 0)
    builder = Builder(soc, csr_csv="csr.csv")
    builder.build(
        sim_config  = sim_config,
        trace       = args.trace,
        trace_fst   = args.trace_fst,
        trace_start = args.trace_start,
        trace_end   = args.trace_end,
        trace_exit  = args.trace_exit,
        sim_end     = args.sim_end
    )

if __name__ == "__main__":
    main()
