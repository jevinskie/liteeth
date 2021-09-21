#!/usr/bin/env python3

import argparse
import time

from litex import RemoteClient

from mdio_regs import BitFieldUnion
from mdio_regs import MDIORegs as R

try:
    from rich import print
except ImportError:
    pass

class MDIOClient:
    MDIO_CLK = 0x01
    MDIO_OE  = 0x02
    MDIO_DO  = 0x04

    MDIO_DI  = 0x01

    MDIO_PREAMBLE   = 0xffffffff
    MDIO_START      = 0x1
    MDIO_READ       = 0x2
    MDIO_WRITE      = 0x1
    MDIO_TURNAROUND = 0x2

    def __init__(self, bus: RemoteClient):
        self.bus = bus
        self.w = bus.regs.mdio_w
        self.r = bus.regs.mdio_r

    @staticmethod
    def reverse_bits(word, nbits):
        r = 0
        while nbits > 0:
            r = (r << 1) | (word & 1)
            word >>= 1
            nbits -= 1
        return r

    def delay(self):
        # probably meaningless w/ RemoteClient overhead
        time.sleep(1e-6)

    def raw_write(self, word: int, bitcount: int):
        word = self.reverse_bits(word, bitcount)
        while bitcount > 0:
            if word & 1:
                self.w.write(self.MDIO_DO | self.MDIO_OE)
                self.delay()
                self.w.write(self.MDIO_CLK | self.MDIO_DO | self.MDIO_OE)
                self.delay()
                self.w.write(self.MDIO_DO | self.MDIO_OE)
            else:
                self.w.write(self.MDIO_OE)
                self.delay()
                self.w.write(self.MDIO_CLK | self.MDIO_OE)
                self.delay()
                self.w.write(self.MDIO_OE)
            word >>= 1
            bitcount -= 1

    def raw_read(self) -> int:
        word = 0
        for i in range(16):
            word <<= 1
            if self.r.read() & self.MDIO_DI:
                word |= 1
            self.w.write(self.MDIO_CLK)
            self.delay()
            self.w.write(0)
            self.delay()
        return word

    def raw_turnaround(self):
        self.delay()
        self.w.write(self.MDIO_CLK)
        self.delay()
        self.w.write(0)
        self.delay()
        self.w.write(self.MDIO_CLK)
        self.delay()
        self.w.write(0)

    def write(self, phyaddr: int, reg: int, val: int):
        self.w.write(self.MDIO_OE)
        self.raw_write(self.MDIO_PREAMBLE, 32)
        self.raw_write(self.MDIO_START, 2)
        self.raw_write(self.MDIO_WRITE, 2)
        self.raw_write(phyaddr, 5)
        self.raw_write(reg, 5)
        self.raw_write(self.MDIO_TURNAROUND, 2)
        self.raw_write(val, 16)
        self.raw_turnaround()

    def read(self, phyaddr: int, reg: int) -> int:
        self.w.write(self.MDIO_OE)
        self.raw_write(self.MDIO_PREAMBLE, 32)
        self.raw_write(self.MDIO_START, 2)
        self.raw_write(self.MDIO_READ, 2)
        self.raw_write(phyaddr, 5)
        self.raw_write(reg, 5)
        self.raw_turnaround()
        r = self.raw_read()
        self.raw_turnaround()
        return r

    def read_reg(self, phyaddr: int, reg: BitFieldUnion):
        packed = self.read(phyaddr, reg.addr)
        return reg(packed=packed)

    def write_reg(self, phyaddr: int, reg: BitFieldUnion):
        self.write(phyaddr, reg.addr, reg.packed)

    def reset(self, phyaddr: int):
        r = self.read_reg(phyaddr, R.CONTROL_COPPER)
        r.reset = 1
        self.write_reg(phyaddr, r)

def main(args):
    bus = RemoteClient()
    bus.open()

    mdioc = MDIOClient(bus)

    phyaddr = args.phyaddr

    # for i in range(32):
    #     r = mdioc.read(0, i)
    #     print(f'{i:02x} => 0x{r:04x}')
    if args.dump:
        print(mdioc.read_reg(phyaddr, R.CONTROL_COPPER))
        print(mdioc.read_reg(phyaddr, R.STATUS_COPPER))
        print(mdioc.read_reg(phyaddr, R.PHY_SPECIFIC_STATUS_COPPER))
        print(mdioc.read_reg(phyaddr, R.EXT_PHY_SPECIFIC_CTRL))
        print(mdioc.read_reg(phyaddr, R.RX_ERROR_COUNTER))
        # print(mdioc.read_reg(phyaddr, R.GLOBAL_STATUS))

    r = mdioc.read_reg(phyaddr, R.EXT_PHY_SPECIFIC_STATUS)
    print(r)
    if args.set_hwconfig:
        r.hw_config = args.hwconfig
        mdioc.write_reg(phyaddr, r)
        mdioc.reset(phyaddr)
        r = mdioc.read_reg(phyaddr, R.EXT_PHY_SPECIFIC_STATUS)

        print(mdioc.read_reg(phyaddr, R.PHY_SPECIFIC_STATUS_COPPER))

    if args.set_rx_delay is not None:
        r = mdioc.read_reg(phyaddr, R.EXT_PHY_SPECIFIC_CTRL)
        r.rgmii_rx_timing_ctrl = args.set_rx_delay
        mdioc.write_reg(phyaddr, r)
        mdioc.reset(phyaddr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--phyaddr", default=0, type=lambda x: int(x, 0), help="PHY address.")
    parser.add_argument("--dump", action="store_true", help="Dump and decode MDIO registers.")
    parser.add_argument("--set-hwconfig", action="store_true", help="Reconfigure HW_CONFIG mode.")
    parser.add_argument("--hwconfig", default=0b1111, type=lambda x: int(x, 0), help="HW_CONFIG mode.")
    parser.add_argument("--set-rx-delay", default=None, type=bool, help="Reconfigure RX delay mode.")
    args = parser.parse_args()
    main(args)
