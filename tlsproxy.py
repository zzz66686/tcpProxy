#!/usr/bin/env  python2
import argparse
import pkgutil
import os
import sys
import threading
import socket
import ssl
import time
import select
import errno

# TODO: implement verbose output
# some code snippets, as well as the original idea, from Black Hat Python




def receive_from(s):
    # receive data from a socket until no more data is there
    b = b""
    while True:
        data = s.recv(4096)
        b += data
        if not data or len(data) < 4096:
            break
    return b



def is_client_hello(sock):
    firstbytes = sock.recv(128, socket.MSG_PEEK)
    return (len(firstbytes) >= 3 and
            firstbytes[0] == 0x16 and
            firstbytes[1:3] in [b"\x03\x00",
                                b"\x03\x01",
                                b"\x03\x02",
                                b"\x03\x03",
                                b"\x02\x00"]
            )


def enable_ssl(remote_socket, local_socket):
    try:
        local_socket = ssl.wrap_socket(local_socket,
                                       server_side=True,
                                       certfile="mitm.pem",
                                       keyfile="mitm.pem",
                                       ssl_version=ssl.PROTOCOL_TLS,
                                       )
    except ssl.SSLError as e:
        raise

    try:
        remote_socket = ssl.wrap_socket(remote_socket)
    except ssl.SSLError as e:
        raise

    return [remote_socket, local_socket]


def starttls(local_socket, read_sockets):
    return (local_socket in read_sockets and
            not isinstance(local_socket, ssl.SSLSocket) and
            is_client_hello(local_socket)
            )

def printHex(s):
    print(s)
    h = ''
    for i in s:
        h += '%02X ' % ord(i)
    print(h)
    

def start_proxy_thread(local_socket):
    # This method is executed in a thread. It will relay data between the local
    # host and the remote host, while letting modules work on the data before
    # passing it on.
    target_ip = '194.156.98.95'
    target_port = 3333    
    remote_socket = socket.socket()

    try:
        remote_socket.connect((target_ip, target_port))
    except Exception as serr:
        raise


    # This loop ends when no more data is received on either the local or the
    # remote socket
    running = True
    while running:
        read_sockets, _, _ = select.select([remote_socket, local_socket], [], [])

        if starttls(local_socket, read_sockets):
            try:
                print('Enable tls')
                ssl_sockets = enable_ssl(remote_socket, local_socket)
                remote_socket, local_socket = ssl_sockets
            except ssl.SSLError as e:
                break

            read_sockets, _, _ = select.select(ssl_sockets, [], [])

        for sock in read_sockets:
            peer = sock.getpeername()
            data = receive_from(sock)

            if sock == local_socket:
                if len(data):
                    print('read from local')
                    printHex(data)
                    remote_socket.send(data)
                else:
                    remote_socket.close()
                    running = False
                    break
            elif sock == remote_socket:
                if len(data):
                    print('read from remote')
                    printHex(data)
                    local_socket.send(data)
                else:
                    local_socket.close()
                    running = False
                    break

def main():
    listen_ip = '0.0.0.0'
    listen_port = 3333

    # this is the socket we will listen on for incoming connections
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy_socket.bind((listen_ip, listen_port))
    except socket.error as e:
        sys.exit(5)

    proxy_socket.listen(10)
    # endless loop until ctrl+c
    try:
        while True:
            in_socket, in_addrinfo = proxy_socket.accept()
            print('connected from' , in_addrinfo)
            proxy_thread = threading.Thread(target=start_proxy_thread,
                                            args=(in_socket,))
            proxy_thread.start()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == '__main__':
    main()
