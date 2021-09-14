#!/usr/bin/env python3

import time

from litex import RemoteClient

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
        self.w = bus.regs.ethphy_mdio_w
        self.r = bus.regs.ethphy_mdio_r

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

def main():
    bus = RemoteClient()
    bus.open()

    mdioc = MDIOClient(bus)

    # for i in range(32):
    #     r = mdioc.read(0, i)
    #     print(f'{i:02x} => 0x{r:04x}')



if __name__ == '__main__':
    main()
