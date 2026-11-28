#!/usr/bin/env python3
"""
norange.py – generate ocserv no-route configuration from China IP lists.

Reads MikroTik .rsc address-list files and produces ocserv-compatible
config snippets using a trie DP that minimises routing error for a given
maximum rule count.

Algorithm
---------
1. Parse .rsc → IPv4 / IPv6 network lists, exact collapse
   (ipaddress.collapse_addresses, zero IP loss).
2. Trie DP: for every prefix-tree node compute

       dp[k] = minimum cost of covering that subtree with exactly k rules

   where cost = (over-covered IPs) + λ · (dropped China IPs)

   Three choices per node:
     • dp[0] = λ · covered        → drop the whole subtree (prune, 0 rules)
     • dp[1] = node_size−covered  → collapse the subtree into one prefix
     • dp[k] = min over k0+k1=k   → split between the two children
                                    (k0 or k1 may be 0 = prune that side)

   λ = 0 disables pruning (every address must be covered, 100% recall).
   Larger λ keeps more China addresses at the price of more over-coverage.

Defaults are the cross-platform tier: --target-v4 512 / --target-v6 384
(~896 rules, safe for every ocserv client build, including the Windows,
Android and iOS ones that cap the number of pushed routes).  With
--prune-v4 1 the DP drops only the tails that cost less to ignore than to
widen a prefix for, which is what keeps recall high at a low rule count;
higher λ (2-4) buys precision instead and is meant for the desktop tier.
--prune-v6 defaults to 0 because the IPv6 source is already compact enough
that pruning only throws away prefixes without buying measurable precision.

Output
------
  no-route = <ip>/<prefix_len>          (IPv4, CIDR, the default)
  no-route = <ip6>/<prefix_len>         (IPv6)
  no-route = <ip>/<dotted_netmask>      (IPv4 with --ipv4-format netmask)

ocserv requires 'address/prefix' or 'address/dotted-netmask' for every
route/no-route entry and rejects a space-separated netmask.  Both IPv4
forms reach the same routing set; CIDR is the default because it is ~25%
shorter, reads better, and drops straight into iptables/ipset/nftables or
RouterOS, while the dotted form only exists for compatibility with tools
that insist on it.  Verified against the upstream parser: ip_route_sanity_check()
in src/ip-util.c on master and ipv4_network_to_strmask() in 1.3.0 both
convert a numeric prefix into the dotted mask internally.

Usage
-----
  python3 norange.py [--target-v4 N] [--target-v6 N]
                     [--prune-v4 λ4] [--prune-v6 λ6]
                     [--in-v4 FILE] [--in-v6 FILE] [--out-dir DIR]
                     [--[no-]include-private]
"""
from __future__ import annotations

import argparse
import ipaddress
import sys
import time
from pathlib import Path

INF = float('inf')

# Extra ranges that should always bypass the tunnel; they are appended
# verbatim and do not count against the rule budget.
PRIVATE_V4 = ('10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16',
              '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '240.0.0.0/4')
PRIVATE_V6 = ('::1/128', 'fc00::/7', 'fe80::/10', 'ff00::/8')


# --------------------------------------------------------------------------- #
#  Trie
# --------------------------------------------------------------------------- #

class _Node:
    __slots__ = ('c0', 'c1', 'exact', 'cnt', 'cov', 'dp', 'act')

    def __init__(self) -> None:
        self.c0: _Node | None = None
        self.c1: _Node | None = None
        self.exact: bool = False   # node itself is an entry of the source list
        self.cnt: int = 0          # number of source entries in subtree
        self.cov: int = 0          # IPs actually covered by those entries
        self.dp: list | None = None
        self.act: list | None = None


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
    node.exact = True


def _dp(node: _Node, plen: int, bits: int, K: int, lam: int) -> None:
    """Bottom-up DP; fills node.dp[0..min(cnt,K)] and the matching actions."""
    for child in (node.c0, node.c1):
        if child is not None:
            _dp(child, plen + 1, bits, K, lam)

    M = min(node.cnt, K)
    dp: list = [INF] * (M + 1)
    act: list = [None] * (M + 1)

    if lam > 0:                      # prune: spend no rule on this subtree
        dp[0] = lam * node.cov
        act[0] = ('prune',)

    if M >= 1:                       # collapse: one prefix for the whole subtree
        dp[1] = (1 << (bits - plen)) - node.cov
        act[1] = ('cover',)
        if node.exact and node.c0 is None and node.c1 is None:
            dp[1] = 0                # already an exact entry, zero waste

    d0 = node.c0.dp if node.c0 is not None else None
    d1 = node.c1.dp if node.c1 is not None else None

    if d0 is not None and d1 is not None:
        for k0 in range(0, min(len(d0) - 1, M) + 1):
            if d0[k0] == INF:
                continue
            for k1 in range(0, min(len(d1) - 1, M - k0) + 1):
                if k1 == 0 and k0 == 0 or d1[k1] == INF:
                    continue
                k = k0 + k1
                c = d0[k0] + d1[k1]
                if c < dp[k]:
                    dp[k] = c
                    act[k] = ('split', k0)
    elif d0 is not None or d1 is not None:
        child = node.c0 if d0 is not None else node.c1
        for k in range(1, min(len(child.dp), M + 1)):
            if child.dp[k] < dp[k]:  # delegate the rule to the populated half
                dp[k] = child.dp[k]
                act[k] = ('via',)

    node.dp = dp
    node.act = act


def _extract(node: _Node, k: int, plen: int, prefix: int, bits: int,
             out: list) -> None:
    """Walk the action table recorded by _dp()."""
    if node is None or k >= len(node.act):
        return
    action = node.act[k]
    if action is None or action[0] == 'prune':
        return
    if action[0] == 'cover' or (node.c0 is None and node.c1 is None):
        out.append((prefix << (bits - plen), plen))
    elif action[0] == 'via':
        child = node.c0 if node.c1 is None else node.c1
        bit = 1 if node.c1 is not None else 0
        _extract(child, k, plen + 1, (prefix << 1) | bit, bits, out)
    else:                                    # 'split'
        k0 = action[1]
        _extract(node.c0, k0, plen + 1, prefix << 1, bits, out)
        _extract(node.c1, k - k0, plen + 1, (prefix << 1) | 1, bits, out)


def trie_compress(nets: list, target: int, bits: int, lam: int = 0) -> list:
    """Compress *nets* (exact-collapsed) to at most *target* CIDR rules."""
    root = _Node()
    for n in nets:
        _insert(root, int(n.network_address), n.prefixlen, bits)

    if root.cnt <= target:
        return sorted(nets)

    _dp(root, 0, bits, target, lam)
    K = min(target, len(root.dp) - 1)
    feasible = [k for k in range(1, K + 1) if root.dp[k] < INF]
    if not feasible or root.dp[0] <= min(root.dp[k] for k in feasible):
        return []

    k_best = min(feasible, key=lambda k: (root.dp[k], -k))
    chosen: list = []
    _extract(root, k_best, 0, 0, bits, chosen)

    cls = ipaddress.IPv4Network if bits == 32 else ipaddress.IPv6Network
    return sorted(cls((addr, plen), strict=False) for addr, plen in chosen)


# --------------------------------------------------------------------------- #
#  Parsing / metrics
# --------------------------------------------------------------------------- #

def parse_rsc(path: Path) -> list:
    """Return the exact-collapsed network list contained in a .rsc file."""
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


def _intervals(nets: list) -> list:
    ivs = sorted((int(n.network_address), int(n.broadcast_address) + 1)
                 for n in nets)
    out: list = []
    for start, end in ivs:
        if out and start <= out[-1][1]:
            if end > out[-1][1]:
                out[-1][1] = end
        else:
            out.append([start, end])
    return out


def _size(ivs: list) -> int:
    return sum(e - s for s, e in ivs)


def _overlap(a: list, b: list) -> int:
    i = j = total = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            total += end - start
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def human(n: float) -> str:
    """Compact address count – IPv6 totals reach 1e33."""
    if n >= 1e15:                       # no useful unit for IPv6 sums
        return f'{float(n):.3g}'
    for unit in ('', 'K', 'M', 'G', 'T', 'P'):
        if n < 1000:
            return f'{n:,.0f}' if unit == '' else f'{n:.1f}{unit}'
        n /= 1000.0
    return f'{n:.1f}P'


def metrics(src: list, out: list) -> dict:
    """Precision / recall of *out* measured against the source list *src*.

    Every emitted rule is a prefix-tree node, so it is always a superset of
    the source entries it stands for: a source entry is either covered in
    full or not at all, which makes the entry-level count meaningful next
    to the address-weighted one.
    """
    truth, cand = _intervals(src), _intervals(out)
    total, covered = _size(truth), _size(cand)
    hit = _overlap(truth, cand)
    entries_hit = sum(
        1 for n in src
        if any(s <= int(n.network_address) and int(n.broadcast_address) + 1 <= e
               for s, e in cand))
    return {
        'src_ips': total,
        'out_ips': covered,
        'hit': hit,
        'miss': total - hit,
        'over': covered - hit,
        'recall': 100.0 * hit / total if total else 100.0,
        'precision': 100.0 * hit / covered if covered else 0.0,
        'extra_pct': 100.0 * (covered - hit) / total if total else 0.0,
        'entries_total': len(src),
        'entries_hit': entries_hit,
        'entries_pct': 100.0 * entries_hit / len(src) if src else 100.0,
    }


# --------------------------------------------------------------------------- #
#  Output
# --------------------------------------------------------------------------- #

def fmt_line(net, v4_fmt: str = 'cidr') -> str:
    """ocserv no-route line, '<addr>/<prefix>' (or '<addr>/<netmask>')."""
    if net.version == 6:
        return f'no-route = {net.network_address}/{net.prefixlen}\n'
    suffix = str(net.netmask) if v4_fmt == 'netmask' else str(net.prefixlen)
    return f'no-route = {net.network_address}/{suffix}\n'


def emit(out_path: Path, comp: list, private: list, label: str,
         src: list, elapsed: float, lam: int, target: int,
         v4_fmt: str = 'cidr') -> dict:
    m = metrics(src, comp)
    fmt_note = ('# format      : dotted netmask' if v4_fmt == 'netmask'
                else '# format      : CIDR')
    header = (
        f'# ocserv no-route – {label}\n'
        f'# source      : {len(src)} entries / {human(m["src_ips"])} addresses\n'
        f'# rules       : {len(comp)} (limit {target}, prune weight {lam})\n'
        f'# china recall: {m["recall"]:.2f}%   precision: {m["precision"]:.2f}%'
        f'   over-coverage: {m["extra_pct"]:.1f}%\n'
        f'# entries kept: {m["entries_hit"]}/{m["entries_total"]}'
        f' ({m["entries_pct"]:.1f}%)\n' +
        fmt_note + '  (no-route = <address>/<mask or prefix>)\n' +
        f'# generated   : .github/scripts/norange.py\n'
    )
    body = ''.join(fmt_line(n, v4_fmt) for n in comp)
    if private:
        body += '\n# local / reserved ranges\n' + ''.join(
            fmt_line(n, v4_fmt) for n in private)
    out_path.write_text(header + body, encoding='utf-8')
    print(f'  {label}: {len(src)} → {len(comp)} rules'
          f'  recall={m["recall"]:.2f}%  precision={m["precision"]:.2f}%'
          f'  over={m["extra_pct"]:.1f}%  entries={m["entries_hit"]}'
          f'/{m["entries_total"]}  miss={human(m["miss"])} IP  [{elapsed:.1f}s]',
          file=sys.stderr)
    print(f'  → {out_path}', file=sys.stderr)
    return m


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('--target-v4', type=int, default=512, metavar='N',
                    help='IPv4 max rules (default: 512)')
    ap.add_argument('--target-v6', type=int, default=384, metavar='N',
                    help='IPv6 max rules (default: 384)')
    ap.add_argument('--prune-v4', type=int, default=1, metavar='λ',
                    dest='prune_v4',
                    help='IPv4 cost of one dropped China address, '
                         '0 = never prune (default: 1)')
    ap.add_argument('--prune-v6', type=int, default=0, metavar='λ',
                    dest='prune_v6',
                    help='IPv6 cost of one dropped China address, '
                         '0 = never prune (default: 0)')
    ap.add_argument('--in-v4', default='all_china.rsc', metavar='FILE',
                    help='IPv4 .rsc source (default: all_china.rsc)')
    ap.add_argument('--in-v6', default='all_china_v6.rsc', metavar='FILE',
                    help='IPv6 .rsc source (default: all_china_v6.rsc)')
    ap.add_argument('--out-dir', default='ocserv', metavar='DIR',
                    help='output directory (default: ocserv/)')
    ap.add_argument('--ipv4-format', choices=('cidr', 'netmask'),
                    default='cidr', dest='ipv4_format',
                    help='IPv4 mask notation (default: cidr)')
    ap.add_argument('--no-include-private', dest='include_private',
                    action='store_false',
                    help='do not append local/reserved bypass ranges')
    ap.set_defaults(include_private=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for fam, src_path, target, bits, name, fname, priv, lam in (
        ('IPv4', args.in_v4, args.target_v4, 32, 'China IPv4',
         'no-route-ipv4.conf', PRIVATE_V4, args.prune_v4),
        ('IPv6', args.in_v6, args.target_v6, 128, 'China IPv6',
         'no-route-ipv6.conf', PRIVATE_V6, args.prune_v6),
    ):
        print(f'{fam}: reading {src_path}', file=sys.stderr)
        src = parse_rsc(Path(src_path))
        print(f'  exact collapse: {len(src)} entries', file=sys.stderr)
        t0 = time.perf_counter()
        comp = trie_compress(src, target, bits, lam)
        private = ([ipaddress.ip_network(c) for c in priv]
                   if args.include_private else [])
        emit(out_dir / fname, comp, private, name, src,
             time.perf_counter() - t0, lam, target, args.ipv4_format)


if __name__ == '__main__':
    main()
