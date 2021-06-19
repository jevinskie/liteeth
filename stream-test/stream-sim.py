#!/usr/bin/env python3

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

etherbone_mac_address = 0x10e2d5000001
g_etherbone_ip_address = '192.168.100.50'

class Streamer(Module):
    def __init__(self, pads, udp_port):
        self.source = stream.Endpoint([("data", 8)])
        self.submodules.streamer_conv = stream.Converter(pads.data.nbits, 8)
        
        target_ip = convert_ip("192.168.100.100")
        print(f'target_ip: {target_ip}')
        # UDP Streamer
        # ------------
        udp_streamer   = LiteEthStream2UDPTX(
            ip_address = target_ip,
            udp_port   = 1234,
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
        counter_preload = 2**17-1
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

        etherbone_ip_address = convert_ip(g_etherbone_ip_address)
        print(f'etherbone_ip_address: {etherbone_ip_address}')
        print(f'etherbone_mac_address: {etherbone_mac_address}')

        # Ethernet PHY
        self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
        # Ethernet MAC
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=8,
                                            interface="crossbar",
                                            endianness=self.cpu.endianness,
                                            hw_mac=etherbone_mac_address)

        # HW ethernet
        self.submodules.arp = LiteEthARP(self.ethmac, etherbone_mac_address, etherbone_ip_address, sys_clk_freq, dw=8)
        self.submodules.ip = LiteEthIP(self.ethmac, etherbone_mac_address, etherbone_ip_address, self.arp.table, dw=8)
        self.submodules.icmp = LiteEthICMP(self.ip, etherbone_ip_address, dw=8)
        self.submodules.udp = LiteEthUDP(self.ip, etherbone_ip_address, dw=8)

        udp_port = self.udp.crossbar.get_port(1234, dw=8)
        self.submodules.streamer = Streamer(self.platform.request("streamer"), udp_port)

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
