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
from litex.soc.interconnect import stream

from liteeth.phy.model import LiteEthPHYModel
from liteeth.mac import LiteEthMAC
from liteeth.core.arp import LiteEthARP
from liteeth.core.ip import LiteEthIP
from liteeth.core.udp import LiteEthUDP
from liteeth.core.icmp import LiteEthICMP
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone
from liteeth.frontend.stream import LiteEthStream2UDPTX
from liteeth.common import convert_ip

from stream_common import *

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("sys_clk", 0, Pins(1)),
    ("sys_rst", 0, Pins(1)),
    ("eth_clocks", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),
    ("streamer", 0,
        Subsignal("valid", Pins(1)),
        Subsignal("data", Pins(64)),
    ),
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

        # Ethernet PHY
        self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
        # Ethernet MAC
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=8,
                                            interface="crossbar",
                                            endianness=self.cpu.endianness,
                                            hw_mac=streamer_source_mac_address)

        source_ip_int: int = convert_ip(streamer_source_ip_address)
        # HW ethernet
        self.submodules.arp = LiteEthARP(self.ethmac, streamer_source_mac_address, source_ip_int, sys_clk_freq, dw=8)
        self.submodules.ip = LiteEthIP(self.ethmac, streamer_source_mac_address, source_ip_int, self.arp.table, dw=8)
        self.submodules.icmp = LiteEthICMP(self.ip, source_ip_int, dw=8)
        self.submodules.udp = LiteEthUDP(self.ip, source_ip_int, dw=8)

        udp_port = self.udp.crossbar.get_port(streamer_port, dw=8)
        self.submodules.streamer = Streamer(sys_clk_freq, streamer_target_ip_address, streamer_port, udp_port, bitrate=streamer_max_packet_size * 8 * 4 * 1024)

        if sim_debug:
            platform.add_debug(self, reset=1 if trace_reset_on else 0)
        else:
            self.comb += platform.trace.eq(1)

        # SRAM -------------------------------------------------------------------------------------
        # self.add_ram("sram", 0x20000000, 0x1000)

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteEth Stream Simulation")
    parser.add_argument("--trace",                action="store_true",     help="Enable Tracing")
    parser.add_argument("--trace-fst",            action="store_true",     help="Enable FST tracing (default=VCD)")
    parser.add_argument("--trace-start",          default="0",             help="Time to start tracing (ps)")
    parser.add_argument("--trace-end",            default="-1",            help="Time to end tracing (ps)")
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
    sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": "192.168.100.100"})

    soc     = BenchSoC(sim_debug=args.sim_debug, trace_reset_on=args.trace_start > 0 or args.trace_end > 0)
    builder = Builder(soc, csr_csv="csr.csv")
    builder.build(
        sim_config  = sim_config,
        trace       = args.trace,
        trace_fst   = args.trace_fst,
        trace_start = args.trace_start,
        trace_end   = args.trace_end
    )

if __name__ == "__main__":
    main()
