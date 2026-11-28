#!/usr/bin/env python3
"""
norange.py – generate ocserv no-route configuration from China IP lists.

Reads MikroTik .rsc address-list files and produces ocserv-compatible
config snippets using trie-based DP to minimise over-coverage for a
given maximum rule count.

Algorithm
---------
1. Parse .rsc → IPv4 / IPv6 network lists.
2. Exact collapse via ipaddress.collapse_addresses (zero IP loss).
3. Trie DP: for every prefix-tree node, compute dp[k] = minimum
   over-coverage (extra IPs outside China) achievable when allocating
   exactly k CIDR rules to that subtree.
   • dp[1]  = node_size − covered   (cover whole subtree with one rule)
   • dp[k]  = min over k0+k1=k of left.dp[k0] + right.dp[k1]
4. Trace back dp table to extract the chosen prefix set.

Output
------
  no-route = <ip> <dotted_netmask>      (IPv4, ocserv space format)
  no-route = <ip6>/<prefix_len>         (IPv6, ocserv slash format)

Usage
-----
  python3 norange.py [--target-v4 N] [--target-v6 N]
                     [--in-v4 FILE] [--in-v6 FILE]
                     [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import ipaddress
import sys
import time
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
#  Trie node
# --------------------------------------------------------------------------- #

INF = float('inf')


class _Node:
    __slots__ = ('c0', 'c1', 'leaf', 'cnt', 'cov', 'dp')

    def __init__(self) -> None:
        self.c0: _Node | None = None
        self.c1: _Node | None = None
        self.leaf: bool = False
        self.cnt: int = 0    # entries in subtree
        self.cov: int = 0    # total IPs occupied by subtree entries
        self.dp: list[int | float] | None = None


def _insert(root: _Node, addr: int, plen: int, bits: int) -> None:
    size = 1 << (bits - plen)
    root.cnt += 1
    root.cov += size
    node = root
    for d in range(plen):
        bit = (addr >> (bits - 1 - d)) & 1
        child = _Node()
        if bit == 0:
            if node.c0 is None:
                node.c0 = child
            node = node.c0
        else:
            if node.c1 is None:
                node.c1 = child
            node = node.c1
        node.cnt += 1
        node.cov += size
    node.leaf = True


def _dp(node: _Node, plen: int, bits: int, K: int) -> None:
    """Bottom-up DP.  Fills node.dp[0..min(cnt,K)] (dp[0]=INF unused)."""
    if node.c0:
        _dp(node.c0, plen + 1, bits, K)
    if node.c1:
        _dp(node.c1, plen + 1, bits, K)

    M = min(node.cnt, K)
    dp: list[int | float] = [INF] * (M + 1)

    # Option: cover whole subtree with this single node
    dp[1] = (1 << (bits - plen)) - node.cov
    if node.leaf and node.c0 is None and node.c1 is None:
        dp[1] = 0  # exact /L entry, zero waste

    d0 = node.c0.dp if node.c0 else None
    d1 = node.c1.dp if node.c1 else None

    if d0 and d1:
        # split budget k = k0 + k1 across both children
        for k0 in range(1, len(d0)):
            v0 = d0[k0]
            if v0 == INF:
                continue
            max_k1 = min(len(d1) - 1, M - k0)
            for k1 in range(1, max_k1 + 1):
                k = k0 + k1
                v = v0 + d1[k1]
                if v < dp[k]:
                    dp[k] = v
    elif d0:
        for k in range(1, min(len(d0), M + 1)):
            if d0[k] < dp[k]:
                dp[k] = d0[k]
    elif d1:
        for k in range(1, min(len(d1), M + 1)):
            if d1[k] < dp[k]:
                dp[k] = d1[k]

    node.dp = dp


def _extract(node: _Node, k: int, plen: int, prefix: int,
             bits: int, out: list[tuple[int, int]]) -> None:
    """Walk DP table to collect chosen (network_int, prefix_len) pairs."""
    c0, c1 = node.c0, node.c1
    if c0 is None and c1 is None:
        out.append((prefix << (bits - plen), plen))
        return

    if c0 and c1:
        d0, d1 = c0.dp, c1.dp
        for k0 in range(1, min(k, len(d0))):
            k1 = k - k0
            if k1 >= 1 and k1 < len(d1) and d0[k0] + d1[k1] == node.dp[k]:
                _extract(c0, k0, plen + 1, prefix << 1, bits, out)
                _extract(c1, k1, plen + 1, (prefix << 1) | 1, bits, out)
                return
    elif c0:
        _extract(c0, k, plen + 1, prefix << 1, bits, out)
        return
    elif c1:
        _extract(c1, k, plen + 1, (prefix << 1) | 1, bits, out)
        return

    # fallback: cover with this node
    out.append((prefix << (bits - plen), plen))


# --------------------------------------------------------------------------- #
#  Parsing
# --------------------------------------------------------------------------- #

def parse_rsc(path: Path) -> list:
    """Return list of ipaddress objects from a MikroTik .rsc address-list."""
    nets: list = []
    for raw in path.read_text(encoding='utf-8').splitlines():
        if not raw.startswith('add address='):
            continue
        addr = raw[len('add address='):].split()[0]
        try:
            nets.append(ipaddress.ip_network(addr, strict=False))
        except ValueError:
            pass
    return sorted(ipaddress.collapse_addresses(nets))


# --------------------------------------------------------------------------- #
#  Core compression
# --------------------------------------------------------------------------- #

def trie_compress(nets: list, target: int, bits: int) -> list:
    """Compress *nets* (already exact-collapsed) to at most *target* entries."""
    root = _Node()
    for n in nets:
        _insert(root, int(n.network_address), n.prefixlen, bits)

    if root.cnt <= target:
        return sorted(nets)

    _dp(root, 0, bits, target)
    K = min(target, len(root.dp) - 1)

    chosen: list[tuple[int, int]] = []
    _extract(root, K, 0, 0, bits, chosen)

    cls = ipaddress.IPv4Network if bits == 32 else ipaddress.IPv6Network
    return sorted(cls((addr, plen), strict=False) for addr, plen in chosen)


# --------------------------------------------------------------------------- #
#  Output
# --------------------------------------------------------------------------- #

def fmt_v4_line(net: ipaddress.IPv4Network) -> str:
    """ocserv IPv4 no-route: '<ip> <dotted_netmask>'."""
    return f'no-route = {net.network_address} {net.netmask}\n'


def fmt_v6_line(net: ipaddress.IPv6Network) -> str:
    """ocserv IPv6 no-route: '<ip6>/<prefix_len>'."""
    return f'no-route = {net.network_address}/{net.prefixlen}\n'


def report(nets_in: list, nets_out: list, label: str, elapsed: float) -> None:
    """Print compression statistics to stderr."""
    orig = sum(n.num_addresses for n in nets_in)
    comp = sum(n.num_addresses for n in nets_out)
    over = (comp - orig) / orig * 100 if orig else 0
    print(
        f'  {label}  {len(nets_in)} → {len(nets_out)} rules'
        f'  [{elapsed:.1f}s]  over-coverage={over:.1f}%',
        file=sys.stderr,
    )


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--target-v4', type=int, default=1000,
                    metavar='N', help='IPv4 max rules (default: 1000)')
    ap.add_argument('--target-v6', type=int, default=500,
                    metavar='N', help='IPv6 max rules (default: 500)')
    ap.add_argument('--in-v4', default='all_china.rsc',
                    metavar='FILE', help='IPv4 .rsc source (default: all_china.rsc)')
    ap.add_argument('--in-v6', default='all_china_v6.rsc',
                    metavar='FILE', help='IPv6 .rsc source (default: all_china_v6.rsc)')
    ap.add_argument('--out-dir', default='ocserv',
                    metavar='DIR', help='output directory (default: ocserv/)')
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    # IPv4 ------------------------------------------------------------------
    print(f'IPv4: reading {args.in_v4}', file=sys.stderr)
    nets4 = parse_rsc(Path(args.in_v4))
    print(f'  collapsed exact: {len(nets4)} entries', file=sys.stderr)
    t0 = time.perf_counter()
    comp4 = trie_compress(nets4, args.target_v4, 32)
    report(nets4, comp4, 'IPv4', time.perf_counter() - t0)
    (out_dir / 'no-route-ipv4.conf').write_text(
        '# ocserv no-route – China IPv4\n'
        f'# rules: {len(comp4)}\n'
        + ''.join(fmt_v4_line(n) for n in comp4),
        encoding='utf-8',
    )
    print(f'  → {out_dir / "no-route-ipv4.conf"}', file=sys.stderr)

    # IPv6 ------------------------------------------------------------------
    print(f'IPv6: reading {args.in_v6}', file=sys.stderr)
    nets6 = parse_rsc(Path(args.in_v6))
    print(f'  collapsed exact: {len(nets6)} entries', file=sys.stderr)
    t0 = time.perf_counter()
    comp6 = trie_compress(nets6, args.target_v6, 128)
    report(nets6, comp6, 'IPv6', time.perf_counter() - t0)
    (out_dir / 'no-route-ipv6.conf').write_text(
        '# ocserv no-route – China IPv6\n'
        f'# rules: {len(comp6)}\n'
        + ''.join(fmt_v6_line(n) for n in comp6),
        encoding='utf-8',
    )
    print(f'  → {out_dir / "no-route-ipv6.conf"}', file=sys.stderr)


if __name__ == '__main__':
    main()
