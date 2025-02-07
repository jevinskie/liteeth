#
# This file is part of LiteEth.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 Florent Kermarrec <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

# RGMII PHY for Altera FPGA

from migen import *
from migen.genlib.cdc import ClockBuffer
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DDROutput, DDRInput

from liteeth.common import *
from liteeth.phy.common import *


class LiteEthPHYRGMIITX(Module):
    def __init__(self, pads):
        self.sink = sink = stream.Endpoint(eth_phy_description(8))

        # # #

        self.specials += [
            DDROutput(
                clk = ClockSignal("eth_tx"),
                i1  = sink.valid,
                i2  = sink.valid,
                o   = pads.tx_ctl),
        ]
        for i in range(4):
            self.specials += [
                DDROutput(
                    clk = ClockSignal("eth_tx"),
                    i1  = sink.data[i],
                    i2  = sink.data[4 + i],
                    o   = pads.tx_data[i]),
            ]
        self.comb += sink.ready.eq(1)


class LiteEthPHYRGMIIRX(Module):
    def __init__(self, pads, rx_delay=2e-9, iodelay_clk_freq=200e6):
        self.source = source = stream.Endpoint(eth_phy_description(8))

        # # #

        self.rx_ctl = rx_ctl         = Signal(2)
        self.rx_ctl_reg = rx_ctl_reg     = Signal(2)
        self.rx_ctl_delay_h = rx_ctl_delay_h = Signal()
        self.rx_data = rx_data        = Signal(8)
        self.rx_data_delay_h = rx_data_delay_h = Signal(4)
        self.rx_data_reg = rx_data_reg    = Signal(8)


        self.specials += [
            DDRInput(
                clk = ClockSignal("eth_rx"),
                i   = pads.rx_ctl,
                o1  = rx_ctl[0],
                o2  = rx_ctl[1]
            )
        ]
        self.sync += [
            rx_ctl_delay_h.eq(rx_ctl[0]),
            rx_ctl_reg[0].eq(rx_ctl_delay_h),
            rx_ctl_reg[1].eq(rx_ctl[1]),
        ]

        for i in range(4):
            self.specials += [
                DDRInput(
                    clk = ClockSignal("eth_rx"),
                    i   = pads.rx_data[i],
                    o1  = rx_data[i],
                    o2  = rx_data[i+4]
                )
            ]
            self.sync += [
                rx_data_delay_h[i].eq(rx_data[i]),
                rx_data_reg[i].eq(rx_data_delay_h[i]),
                rx_data_reg[i+4].eq(rx_data[i+4]),
            ]

        rx_ctl_reg_d = Signal(2)
        self.sync += rx_ctl_reg_d.eq(rx_ctl_reg)

        last = Signal()
        self.comb += last.eq(~rx_ctl_reg[0] & rx_ctl_reg_d[0])
        self.sync += [
            source.valid.eq(rx_ctl_reg[0]),
            source.data.eq(rx_data_reg)
        ]
        self.comb += source.last.eq(last)


class LiteEthPHYRGMIICRG(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset, cd_eth_rx: ClockDomain, cd_eth_tx: ClockDomain, tx_delay=2e-9, hw_reset_cycles=256):
        self._reset = CSRStorage()

        self.cd_eth_rx = cd_eth_rx
        self.cd_eth_tx = cd_eth_tx

        # # #
        self.comb += cd_eth_rx.clk.eq(clock_pads.rx)
        self.rxclkbuf = ClockBuffer(cd_eth_rx)
        self.specials += self.rxclkbuf

        # self.comb += clock_pads.gtx.eq(ClockSignal("eth_tx_delayed"))
        self.gtx_ddr_ioe = DDROutput(
            clk = ClockSignal("eth_tx_delayed"),
            i1  = 1,
            i2  = 0,
            o   = clock_pads.gtx)
        self.specials += self.gtx_ddr_ioe

        # Clock counters (debug)
        self.rx_cnt = Signal(8)
        self.tx_cnt = Signal(8)
        self.sync.eth_rx += self.rx_cnt.eq(self.rx_cnt + 1)
        self.sync.eth_tx += self.tx_cnt.eq(self.tx_cnt + 1)

        # Reset
        self.reset = reset = Signal()
        if with_hw_init_reset:
            self.submodules.hw_reset = LiteEthPHYHWReset(cycles=hw_reset_cycles)
            self.comb += reset.eq(self._reset.storage | self.hw_reset.reset)
        else:
            self.comb += reset.eq(self._reset.storage)
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(~reset)
        self.specials += [
            AsyncResetSynchronizer(ClockDomain("eth_tx"), reset),
            AsyncResetSynchronizer(ClockDomain("eth_rx"), reset),
        ]


class LiteEthPHYRGMII(Module, AutoCSR):
    dw          = 8
    tx_clk_freq = 125e6
    rx_clk_freq = 125e6
    def __init__(self, clock_pads, pads, cd_eth_rx: ClockDomain, cd_eth_tx: ClockDomain, with_hw_init_reset=True, tx_delay=2e-9, rx_delay=2e-9,
            iodelay_clk_freq=200e6, hw_reset_cycles=256):
        self.clock_pads = clock_pads
        self.submodules.crg = LiteEthPHYRGMIICRG(clock_pads, pads, with_hw_init_reset, cd_eth_rx, cd_eth_tx, tx_delay, hw_reset_cycles)
        self.submodules.tx  = ClockDomainsRenamer("eth_tx")(LiteEthPHYRGMIITX(pads))
        self.submodules.rx  = ClockDomainsRenamer("eth_rx")(LiteEthPHYRGMIIRX(pads, rx_delay))
        self.sink, self.source = self.tx.sink, self.rx.source

        if hasattr(pads, "mdc"):
            self.submodules.mdio = LiteEthPHYMDIO(pads)
