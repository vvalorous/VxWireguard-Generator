#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2018 Star Brilliant
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import binascii
import errno
import sys
from typing import List, Optional
from . import common


def main(argv: List[str]) -> int:
    if len(argv) != 4 or argv[2] == '--help':
        print_usage()
        return 0

    network_name, node_name = argv[2], argv[3]
    config = common.Config()

    if not config.load(network_name):
        print("vwgen: Unable to find configuration file '{}.conf'".format(network_name), file=sys.stderr)
        return errno.ENOENT

    network = config.network()
    nodes = config.nodes()
    blacklist = config.blacklist()

    if node_name not in nodes:
        print("vwgen: Network '{}' does not have node '{}'".format(network_name, node_name), file=sys.stderr)
        return errno.ENOENT
    node = nodes[node_name]

    print('# Network {}, generated by VxWireguard-Generator'.format(config.network_name()))

    print()

    print('# Node {}'.format(node_name))

    print('[Interface]')

    print('ListenPort = {:d}'.format(node.get('ListenPort', 0)))

    if 'PrivateKey' in node:
        print('PrivateKey = {}'.format(node['PrivateKey']))

    if 'LinkLayerAddress' in node:
        print('Address = {}'.format(', '.join(node['LinkLayerAddress'])))

    print('MTU = {}'.format(int(network.get('VxlanMTU', 1500)) + 50))

    print('Table = off')

    if node.get('FwMark', 0) != 0:
        print('FwMark = {:x}'.format(node['FwMark']))

    if node.get('SaveConfig', False):
        print('SaveConfig = true')

    for script in node.get('PreUp', []):
        print('PreUp = {}'.format(script))

    mac_address = common.generate_pubkey_macaddr(node)
    mac_address_cmdline = ''
    if mac_address:
        mac_address_cmdline = 'address {} '.format(mac_address)

    print('PreUp = ip link add v%i {}mtu {} type vxlan id {} dstport {} ttl 1 noudpcsum || true'.format(mac_address_cmdline, network.get('VxlanMTU', 1500), network.get('VxlanID', 0), network.get('VxlanPort', 4789)))

    print('PreUp = ethtool -K v%i tx off rx off')

    print('PreUp = sysctl -w net.ipv4.conf.v%i.accept_redirects=0 net.ipv4.conf.v%i.send_redirects=0 net.ipv6.conf.v%i.accept_redirects=0')

    for address in node.get('Address', []):
        print('PreUp = ip address add {} dev v%i || true'.format(address))

    pubkey_ipv6 = common.generate_pubkey_ipv6(network, node)
    if pubkey_ipv6:
        print('PreUp = ip address add {} dev v%i || true'.format(pubkey_ipv6))

    if node.get('UPnP', False) and node.get('ListenPort', 0) != 0:
        print('PreUp = upnpc -r {} udp &'.format(node['ListenPort']))

    for peer_name, peer in nodes.items():
        if peer_name == node_name:
            continue
        in_blacklist = common.NamePair(node_name, peer_name) in blacklist
        comment_prefix = '#' if in_blacklist else ''

        for address in peer.get('LinkLayerAddress', []):
            print('{}PostUp = bridge fdb append 00:00:00:00:00:00 dev v%i dst {} via %i'.format(comment_prefix, str(address).split('/', 1)[0]))

    print('PostUp = ip link set v%i up')

    for script in node.get('PostUp', []):
        print('PostUp = {}'.format(script))

    for script in node.get('PreDown', []):
        print('PreDown = {}'.format(script))

    print('PreDown = ip link set v%i down')

    print('PostDown = ip link delete v%i')

    for script in node.get('PostDown', []):
        print('PostDown = {}'.format(script))

    print()

    for peer_name, peer in nodes.items():
        if peer_name == node_name:
            continue
        in_blacklist = common.NamePair(node_name, peer_name) in blacklist
        comment_prefix = '#' if in_blacklist else ''

        print('{}# Peer node {}'.format(comment_prefix, peer_name))

        print('{}[Peer]'.format(comment_prefix))

        if peer.get('PrivateKey'):
            secret_base64: str = peer['PrivateKey']
            secret: bytes = binascii.a2b_base64(secret_base64)
            if len(secret) != 32:
                print("vwgen: Node '{}' has incorrect PrivateKey".format(peer_name), file=sys.stderr)
            else:
                pubkey = binascii.b2a_base64(common.pubkey(secret), newline=False).decode('ascii')
                print('{}PublicKey = {}'.format(comment_prefix, pubkey))

        if peer.get('AllowedIPs'):
            print('{}AllowedIPs = {}'.format(comment_prefix, ', '.join(peer['AllowedIPs'])))

        if peer.get('Endpoint'):
            print('{}Endpoint = {}'.format(comment_prefix, peer['Endpoint']))

        if peer.get('PersistentKeepalive', 0) != 0:
            print('{}PersistentKeepalive = {}'.format(comment_prefix, node['PersistentKeepalive']))

        print()

    print('# Network {}, node {}, generated by VxWireguard-Generator'.format(config.network_name(), node_name))

    return 0


def print_usage() -> None:
    print('Usage: vwgen showconf <network> <node>')


if __name__ == '__main__':
    sys.exit(main(sys.argv))
