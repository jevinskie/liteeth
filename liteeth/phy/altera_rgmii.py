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

        tx_ctl_obuf  = Signal()
        tx_data_obuf = Signal(4)

        self.specials += [
            Instance("ODDR",
                p_DDR_CLK_EDGE = "SAME_EDGE",
                i_C  = ClockSignal("eth_tx"),
                i_CE = 1,
                i_S  = 0,
                i_R  = 0,
                i_D1 = sink.valid,
                i_D2 = sink.valid,
                o_Q  = tx_ctl_obuf,
            ),
            Instance("OBUF",
                i_I = tx_ctl_obuf,
                o_O = pads.tx_ctl,
            ),
        ]
        for i in range(4):
            self.specials += [
                Instance("ODDR",
                    p_DDR_CLK_EDGE = "SAME_EDGE",
                    i_C  = ClockSignal("eth_tx"),
                    i_CE = 1,
                    i_S  = 0,
                    i_R  = 0,
                    i_D1 = sink.data[i],
                    i_D2 = sink.data[4+i],
                    o_Q  = tx_data_obuf[i],
                ),
                Instance("OBUF",
                    i_I = tx_data_obuf[i],
                    o_O = pads.tx_data[i],
                )
            ]
        self.comb += sink.ready.eq(1)


class LiteEthPHYRGMIIRX(Module):
    def __init__(self, pads, rx_delay=2e-9, iodelay_clk_freq=200e6):
        self.source = source = stream.Endpoint(eth_phy_description(8))

        # # #

        self.rx_ctl = rx_ctl         = Signal(2)
        self.rx_ctl_reg = rx_ctl_reg     = Signal(2)
        self.rx_data = rx_data        = Signal(8)
        self.rx_data_reg = rx_data_reg    = Signal(8)

        self.specials += [
            DDRInput(
                clk = ClockSignal("eth_rx"),
                i   = pads.rx_ctl,
                o1  = rx_ctl[0],
                o2  = rx_ctl[1]
            )
        ]
        self.sync += rx_ctl_reg.eq(rx_ctl)
        for i in range(4):
            self.specials += [
                DDRInput(
                    clk = ClockSignal("eth_rx"),
                    i   = pads.rx_data[i],
                    o1  = rx_data[i],
                    o2  = rx_data[i+4]
                )
            ]
        self.sync += rx_data_reg.eq(rx_data)

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
    def __init__(self, clock_pads, pads, with_hw_init_reset, cd_eth_rx: ClockDomain, tx_delay=2e-9, hw_reset_cycles=256):
        self._reset = CSRStorage()

        # # #
        self.comb += cd_eth_rx.clk.eq(clock_pads.rx)
        self.rxclkbuf = ClockBuffer(cd_eth_rx)
        self.specials += self.rxclkbuf

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
    def __init__(self, clock_pads, pads, cd_eth_rx: ClockDomain, with_hw_init_reset=True, tx_delay=2e-9, rx_delay=2e-9,
            iodelay_clk_freq=200e6, hw_reset_cycles=256):
        self.clock_pads = clock_pads
        self.submodules.crg = LiteEthPHYRGMIICRG(clock_pads, pads, with_hw_init_reset, cd_eth_rx, tx_delay, hw_reset_cycles)
        # self.submodules.tx  = ClockDomainsRenamer("eth_tx")(LiteEthPHYRGMIITX(pads))
        self.submodules.rx  = ClockDomainsRenamer("eth_rx")(LiteEthPHYRGMIIRX(pads, rx_delay))
        # self.sink, self.source = self.tx.sink, self.rx.source

        if hasattr(pads, "mdc"):
            self.submodules.mdio = LiteEthPHYMDIO(pads)
