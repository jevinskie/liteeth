#!/usr/bin/env python3

import array
import socket
import sys

import pretty_errors
from rich import print

from stream_common import *

def endian_swap(n: int, sz = None, signed=False) -> int:
    dest_endianness = {'little': 'big', 'big': little}[sys.byteorder]
    if sz is None:
        sz = (n.bit_length() + 7) // 8
    swapped_bytes = n.to_bytes(sz, byte_order=dest_endianness, signed=signed)
    return int.from_bytes(swapped_bytes, byte_order=sys.byteorder, signed=signed)

def test_udp_stream_counter():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', streamer_port))
    last_int = None
    payload_sz = 8

    packet_num = 0
    while True:
        data, server = sock.recvfrom(4096)
        da = array.array('Q', data)
        # da[:] = map(lambda n: endian_swap(n, 8), da)
        # da.byteswap()

        print(f'len(data): {len(data)} da[0]: {da[0]:#x}')

        for i in range(1, len(da)):
            # assert da[i-1] + 1 == da[i]
            if da[i-1] +1 != da[i]:
                print(f'da[i-1] + 1 != da[i] da[i-1]: {da[i-1]:#x} da[i]: {da[i]:#x} i: {i} packet_num: {packet_num}')

        if last_int is not None:
            # assert last_int + 1 == da[0]
            if last_int + 1 != da[0]:
                print(f'last_int + 1 != da[0] last_int: {last_int:#x} da[0]: {da[0]:#x} packet_num: {packet_num}')
        last_int = da[-1]
        packet_num += 1

if __name__ == '__main__':
    sys.exit(test_udp_stream_counter())
