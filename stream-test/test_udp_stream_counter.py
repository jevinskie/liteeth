#!/usr/bin/env python3

import array
import socket
import sys

import pretty_errors
from rich import print

from stream_common import *

def test_udp_stream_counter():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', streamer_port))
    last_int = None
    payload_sz = 8

    while True:
        data, server = sock.recvfrom(4096)
        da = array.array('Q', data)
        print(f'len(data): {len(data)} da[0]: {da[0]:#x}')

        for i in range(1, len(da)):
            assert da[i-1] + 1 == da[i]

        if last_int is not None:
            assert last_int + 1 == da[0]
        last_int = da[-1]

if __name__ == '__main__':
    sys.exit(test_udp_stream_counter())
