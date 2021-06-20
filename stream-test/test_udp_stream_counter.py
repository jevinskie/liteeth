#!/usr/bin/env python3

import array
import socket
import sys

import pretty_errors
from rich import print

from stream_common import *

def test_udp_stream_counter():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (streamer_target_ip_address, streamer_port)
    data, server = sock.recvfrom(4096)
    print(f'len(data): {len(data)} server: {server}')

if __name__ == '__nain__':
    sys.exit(test_udp_stream_counter())
