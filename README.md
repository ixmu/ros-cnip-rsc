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

`.github/workflows/norange.yml` 有三种触发方式：

1. **列表更新后自动重建**——`ROS CNIP List` 运行成功即触发（`workflow_run`）；
2. **生成逻辑变更时自动重建**——`.github/**`（生成器脚本或本工作流）推送到 `main` 即触发；
3. **手动重建**——**Actions → NoRoute Config → Run workflow**，可临时覆盖通用档的条目数与裁剪权重。

生成结果只提交到 `ocserv/`，不在 push 的 `paths` 过滤范围内，因此不会形成自触发循环。

推送产物使用仓库密钥 `ACTION_TOKEN`（或 `GH_TOKEN`，二者任一即可）；两者都没配置时自动退回 `GITHUB_TOKEN`，此时需要把 Settings → Actions → General → Workflow permissions 设为 **Read and write**。`Clean Workflows` 每 7 天清理一次三个工作流中失败/超时的运行记录（成功记录由 GitHub 自身的保留策略管理）。

### 两套产物

| 目录 | 定位 | IPv4 | IPv6 | 路由条数¹ | 中国IP覆盖率 v4 / v6 | 精确率 v4 / v6 | 下发体积² |
|------|------|-----:|-----:|---------:|:-------------------:|:-------------:|--------:|
| `ocserv/` | 通用档（全终端安全） | 512 | 384 | 908 | 94.38% / 100.00% | 97.67% / 97.74% | 43 KB |
| `ocserv/desktop/` | 桌面档（更准、条数更多） | 800 | 512 | 1324 | 98.49% / 100.00% | 98.50% / 99.24% | 63 KB |

> ¹ 含文件末尾附带的 12 条本地/保留段（IPv4 8 条 + IPv6 4 条），这部分不计入条数预算。
> ² ocserv 把每条路由作为一行 `X-CSTP-Split-Exclude:` 下发，实测约 48~50 B/条；表中为该档 v4+v6 合计。

指标以全量列表 `all_china.rsc` / `all_china_v6.rsc` 为基准：

- **中国IP覆盖率**——列表里的中国 IP 有多少被 no-route 命中，低说明有国内流量白跑隧道（只是变慢，仍可用）；
- **精确率**——no-route 命中的地址里有多少确实是中国 IP，低说明有境外 IP 被误判直连（翻墙失效的主要原因，危害更大）；
- **超覆盖**——多包含的地址数量占中国 IP 总量的比例。

### 为什么默认是 512 + 384（约 900 条）

- **服务端没有条数上限**：`config.c` 对 `no-route` 只做语法检查、不限量，`send_routes()`（`worker-vpn.c`）逐条拼 `X-CSTP-Split-Exclude` 头。条目多只会线性增大下发体积，ocserv 4.10 与最新版本在这点上没有差别。
- **约束在客户端**：Android 平台 VPN profile 的硬上限是 128 KB（AOSP `Vpn.java`：`MAX_VPN_PROFILE_SIZE_BYTES = 1 << 17`，超限直接报 `Profile too big`）。按实测约 50 B/条折算，纯路由可容约 2600 条；通用档 908 条只占 43 KB，给证书、DNS、域名留出充足余量。iOS / Android 上的 AnyConnect 系客户端在移动端的处理开销明显高于桌面端，官方未公布固定条数上限，这里按业内经验把「全终端安全线」定在 1000 条以内。
- **精度收益的拐点就在这里**：IPv6 精确率从 320 条的 85.9% 跳到 384 条的 97.7%，之后每加 64 条只涨约 1 个点；IPv4 在 λ=1 下 512 → 800 条只多换 3.7 个点覆盖率。低于 384 / 512 会明显丢精度，高于 1300 只是买边际收益、同时把移动端余量吃光。
- 结论：**通用档 512 v4 + 384 v6 ≈ 900 条**；桌面 / 路由器客户端用 `config-per-group` 指到 `ocserv/desktop/`（1324 条）。移动端占比高的服务可把通用档压到 320 条（λ=1 为 88.76% / 96.39%），手动运行时填 `target_v4=320` 即可。

### 算法

`.github/scripts/norange.py`：前缀树 + 动态规划。对树上每个节点求 `dp[k] = 用 k 条规则覆盖该子树的最小代价`，代价定义为

```
代价 = 超覆盖地址数 + λ × 被丢弃的中国地址数
```

每个节点有三种选择：整体折叠成 1 条前缀、在两个孩子子树之间分配 k 条、或整棵子树直接丢弃（用 0 条）。
所以条数是**硬上限**，算法可以选择放弃零碎小段，而不是用一条巨大的汇总段去包它——这正是准确率的来源。

默认 `λ = 1`。通用档 512 条里被丢弃的最大块只有 /16，合计 16,012,544 IP（中国 IP 的 5.62%），其中 1025 条是 ≤/24 的零碎段、合计仅 262,400 IP；换来精确率从同条数不裁剪时的 55.27% 提升到 97.67%。被丢弃的主要是阿里 / 腾讯云等机房段（`1.45.0.0/16`、`8.208.0.0/16`、`8.214.0.0/16`、`8.219.0.0/16`、`14.103.0.0/16`），这些地址走隧道通常反而更合理。
桌面档 `λ = 2` 时最大丢弃段降到 /18，裁剪比例 1.51%，精确率 98.50%。

λ 越大越保守（少裁剪、覆盖率高、精确率低）；`λ = 0` 关闭裁剪，必然 100% 覆盖。IPv6 源列表本身足够紧凑，两套都固定 `λ = 0`。

### 条数 × λ 实测对照（IPv4，格式：中国IP覆盖率 / 精确率）

| 目标条数 | 256 | 320 | 448 | **512** | 640 | **800** | 1000 |
|---------:|:---:|:---:|:---:|:-----:|:---:|:-----:|:----:|
| λ=1 | 86.60 / 94.95 | 88.76 / 96.39 | 93.00 / 97.54 | **94.38 / 97.67** | 96.64 / 98.41 | 98.03 / 99.17 | 98.73 / 99.65 |
| λ=2 | 90.93 / 89.21 | 93.23 / 90.57 | 95.20 / 94.21 | 96.49 / 94.63 | 97.67 / 96.94 | **98.49 / 98.50** | 99.07 / 99.12 |
| λ=4 | 95.51 / 79.63 | 95.69 / 85.48 | 97.89 / 88.06 | 98.07 / 91.24 | 98.67 / 94.33 | 99.00 / 97.08 | 99.33 / 98.43 |

IPv6（`λ = 0`，覆盖率恒为 100%）：

| 目标条数 | 256 | 320 | **384** | 448 | **512** | 640 | 800 |
|---------:|:---:|:---:|:-----:|:---:|:------:|:---:|:---:|
| 精确率 | 35.16% | 85.94% | **97.74%** | 98.75% | **99.24%** | 99.76% | 99.96% |
| 超覆盖 | 184% | 16.4% | 2.3% | 1.3% | 0.8% | 0.2% | 0.0% |

### 与手工 NoRoute 列表对比

对比对象：`ixmu/Note` 仓库 `Ocserv/ocserv/config-per-group/NoRoute`（198 条，按 /11 粒度手工汇总，不含本地段）。

| 方案 | 条数 | 中国IP覆盖率 | 精确率 |
|------|-----:|-------------:|-------:|
| 手工 NoRoute 列表 | 198 | 95.19% | 43.87% |
| 本算法 λ=1 | 198 | 83.08% | **92.87%** |
| 本算法 λ=2 | 198 | 88.86% | 85.75% |
| 本算法 λ=4 | 198 | 93.53% | 77.12% |
| 本算法通用档 λ=1 | 512 | 94.38% | 97.67% |
| 本算法桌面档 λ=2 | 800 | **98.49%** | **98.50%** |

手工列表用大段汇总换覆盖率，精确率仅 43.87%——过半境外 IP 会被判成直连。相同条数下本算法可做到 92.87% 精确率；要追平它的 95.19% 覆盖率约需 480 条（λ=4 下 448 条已达 97.89%）。

### 格式与使用

默认输出 CIDR 写法，IPv4 / IPv6 一致：

```ini
# IPv4
no-route = 1.12.0.0/14
# IPv6
no-route = 2001:250::/30
```

ocserv 的 route/no-route 只接受 `地址/前缀` 或 `地址/点分掩码` 两种写法（空格分隔的掩码会被判非法并丢弃）。两种写法解析后的路由集合完全相同，对准确率没有影响，CIDR 只带来两点实际好处：文件小 26%，以及可直接复制到 iptables / ipset / nftables / RouterOS。上游解析代码 `src/ip-util.c`（master 的 `ip_route_sanity_check()`、1.3.0 的 `ipv4_network_to_strmask()`）都会把数字前缀在内部转换成点分掩码，因此 ocserv 4.10 这类老版本同样可用。需要点分掩码时加 `--ipv4-format netmask`。

全局配置（所有用户使用通用档）：

```ini
include = /etc/ocserv/no-route-ipv4.conf
include = /etc/ocserv/no-route-ipv6.conf
```

按分组给桌面端更长的列表：`config-per-group` 里的 `no-route` 默认**替换**全局值，需要与全局叠加时把 `append-routes = true` 打开。

```ini
# /etc/ocserv/config-per-group/desktop
# 内容即 ocserv/desktop/no-route-ipv4.conf + no-route-ipv6.conf
no-route = 1.12.0.0/14
...
```

移动端分组不写 `no-route`，继承全局通用档即可。

文件末尾附带的本地/保留段（`10/8`、`100.64/10`、`127/8`、`169.254/16`、`172.16/12`、`192.168/16`、`224/4`、`240/4`，IPv6 为 `::1/128`、`fc00::/7`、`fe80::/10`、`ff00::/8`）不计入条数预算，用 `--no-include-private` 可关闭，且已验证与中国规则无重叠。

本地重新生成：

```bash
# 通用档（等于默认参数）
python3 .github/scripts/norange.py
# 桌面档
python3 .github/scripts/norange.py --out-dir ocserv/desktop \
    --target-v4 800 --target-v6 512 --prune-v4 2
# 精简档（约 330 条，移动端优先）
python3 .github/scripts/norange.py --out-dir ocserv/lite \
    --target-v4 320 --target-v6 0 --prune-v4 1
```

### 如何调参

no-route 误判（境外 IP 被直连）通常比漏命中（国内 IP 白跑隧道）更影响体验，因此默认取偏保守的 `λ = 1`。

- 某些境外站点直连了 → λ 调到 0~1，或降低条数；
- 国内流量偏多、隧道负载高 → λ 调到 2~4，或直接放宽条数；
- 只服务桌面 / 路由器客户端 → 直接用 `ocserv/desktop/`；
- 移动端占主导 → 通用档压到 320 条，甚至 `target_v6=0` 只发 IPv4。
