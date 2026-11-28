# ROS-cnip-script搬运自 www.tcp5.com 列表，加入ROS的导入命令制作而成。


>此列表仅包含IPV4地址，没有IPV6地址。

>自动修改为ROS命令脚本文件，不定期更新。

>加了一条在导入前清空名为“CNIP”列表的命令，避免出现新旧列表交叉冲突。

>加了一条导入列表时关闭日志输出的指令，避免日志刷屏。


附：ROS导入脚本

>请确保ROS网络可以正常访问github。

###### 在/System Script下添加如下脚本内容
```
/tool fetch url="https://ghub.10105410.xyz/ixmu/ros-cnip-rsc/raw/refs/heads/main/all_china.rsc"
/system logging disable 0
/ip firewall address-list
remove [find list=List_ALL_China]
/import all_china.rsc
/system logging enable 0
/file remove [find name="all_china.rsc"]
:local ListAllChina [:len [/ip firewall address-list find list="List_ALL_China"]]
:log info ("List_ALL_China更新:"."$ListAllChina"."条")


/tool fetch url="https://ghub.10105410.xyz/ixmu/ros-cnip-rsc/raw/refs/heads/main/all_china_v6.rsc"
/system logging disable 0
/ipv6 firewall address-list
remove [find list=List_ALL_China]
/import all_china_v6.rsc
/system logging enable 0
/file remove [find name="all_china_v6.rsc"]
:local ListAllChina [:len [/ipv6 firewall address-list find list="List_ALL_China"]]
:log info ("List_ALL_China_V6更新:"."$ListAllChina"."条")
```
建议手动执行，也可以在/System Scheduler下添加一个脚本定时

---

## ocserv NoRoute 配置

`.github/workflows/norange.yml` 在每次列表更新后自动重新生成，也可手动触发：**Actions → NoRoute Config → Run workflow**（可临时覆盖条数/权重参数）。

| 文件 | 规则数 | 中国IP覆盖率 | 精确率 | 超覆盖 |
|------|-------:|-------------:|-------:|-------:|
| `ocserv/no-route-ipv4.conf` | 800（另加 8 条本地段） | 99.00% | 97.08% | 3.0% |
| `ocserv/no-route-ipv6.conf` | 800（另加 4 条本地段） | 100.00% | 99.96% | 0.0% |

指标以全量列表 `all_china.rsc` / `all_china_v6.rsc` 为基准：

- **中国IP覆盖率**——列表里的中国 IP 有多少被 no-route 命中，低说明有国内流量白跑隧道；
- **精确率**——no-route 命中的地址里有多少确实是中国 IP，低说明有境外 IP 被误判直连（翻墙失效的主要原因）；
- **超覆盖**——多包含的地址数量占中国 IP 总量的比例。

### 算法

`.github/scripts/norange.py`：前缀树 + 动态规划。对树上每个节点求 `dp[k] = 用 k 条规则覆盖该子树的最小代价`，代价定义为

```
代价 = 超覆盖地址数 + λ × 被丢弃的中国地址数
```

每个节点有三种选择：整体折叠成 1 条前缀、在两个孩子子树之间分配 k 条、或整棵子树直接丢弃（用 0 条）。
所以条数是**硬上限**，而算法可以选择放弃零碎小段，而不是用一条巨大的汇总段去包它——这正是准确率的来源。
被丢弃的最大块只有 /19（8192 个地址），合计只占中国 IP 的 1.00%，却换来了精确率从 72.77%（不裁剪时的同条数结果）提升到 97.08%。

λ 越大越保守（少裁剪、覆盖率高、精确率低）；`λ = 0` 关闭裁剪，必然 100% 覆盖。
IPv6 源列表本身足够紧凑，默认 `λ = 0`。

### 条数 / 精度对照（IPv4，λ=4）

| 目标条数 | 200 | 400 | 600 | **800** | 1000 | 1200 |
|---------:|----:|----:|----:|------:|-----:|-----:|
| 中国IP覆盖率 | 93.66% | 97.24% | 98.63% | **99.00%** | 99.33% | 99.52% |
| 精确率 | 77.11% | 86.55% | 92.97% | **97.08%** | 98.43% | 98.98% |
| 超覆盖 | 27.8% | 15.1% | 7.5% | **3.0%** | 1.6% | 1.0% |

### 与手工 NoRoute 列表对比

对比对象：`ixmu/Note` 仓库 `Ocserv/ocserv/config-per-group/NoRoute`（198 条，按 /11 粒度手工汇总，不含中国列表外的本地段）。

| 方案 | 条数 | 中国IP覆盖率 | 精确率 |
|------|-----:|-------------:|-------:|
| 手工 NoRoute 列表 | 198 | 95.19% | 43.87% |
| 本算法 λ=4 | 200 | 93.66% | **77.11%** |
| 本算法 λ=4 | 800 | **99.00%** | **97.08%** |

相同条数下精确率高出 33 个百分点；要追上手工列表的 95.19% 覆盖率只需约 300 条。

### 格式与使用

默认输出 CIDR 写法，IPv4 / IPv6 一致：

```ini
# IPv4
no-route = 1.12.0.0/14
# IPv6
no-route = 2001:250::/30
```

ocserv 的 route/no-route 只接受 `地址/前缀` 或 `地址/点分掩码` 两种写法（空格分隔的掩码会被判非法并丢弃）。两种写法解析后的路由集合完全相同，对准确率没有任何影响，CIDR 只带来两点实际好处：文件小 26%（20.9 KB vs 28.4 KB），以及可直接复制到 iptables / ipset / nftables / RouterOS 使用。上游解析代码 `src/ip-util.c`（master 的 `ip_route_sanity_check()`、1.3.0 的 `ipv4_network_to_strmask()`）都会把数字前缀在内部转换成点分掩码，因此老版本 ocserv 同样可用。需要点分掩码时加 `--ipv4-format netmask`。

文件末尾附带的本地/保留段（`10/8`、`100.64/10`、`127/8`、`169.254/16`、`172.16/12`、`192.168/16`、`224/4`、`240/4`，IPv6 为 `::1/128`、`fc00::/7`、`fe80::/10`、`ff00::/8`）不计入条数预算，用 `--no-include-private` 可关闭，且已验证与中国规则无重叠。

在 ocserv.conf 中引入（分路由：中国 IP 不走隧道）：
```ini
include = /path/to/no-route-ipv4.conf
include = /path/to/no-route-ipv6.conf
```

本地重新生成：
```bash
python3 .github/scripts/norange.py --target-v4 800 --target-v6 800 --prune-v4 4 --prune-v6 0
```

### λ 与条数的选择

800 条预算下不同 λ 的实测结果（IPv4）：

| λ | 中国IP覆盖率 | 精确率 | 超覆盖 | 说明 |
|---:|---:|---:|---:|---|
| 0 | 100.00% | 72.77% | 37.4% | 不裁剪，为包住每个碎片牺牲精确率 |
| 1 | 98.03% | **99.17%** | 0.8% | 精确率优先：几乎不会误伤境外 IP |
| 2 | 98.49% | 98.50% | 1.5% | 折中 |
| **4** | 99.00% | 97.08% | 3.0% | 默认，覆盖率优先 |
| 8 | 99.35% | 95.02% | 5.2% | 更保守 |

经验判断：no-route 命中错误（境外 IP 被直连）通常比漏命中（国内 IP 白跑隧道）更影响使用体验，所以如果发现某些境外站点直连了，把 λ 调小到 1~2；如果发现国内流量偏多，调大到 8，或者直接放宽条数（1000 条 @λ=4 = 99.33%/98.43%，1200 条 = 99.52%/98.98%）。

