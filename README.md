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
3. **手动重建**——**Actions → NoRoute Config → Run workflow**，可临时覆盖标准档的条目数与裁剪权重。

生成结果只提交到 `ocserv/`，不在 push 的 `paths` 过滤范围内，因此不会形成自触发循环。

**凭据**：三个工作流统一按 `ACTION_TOKEN` → `GH_TOKEN` → 内置 `GITHUB_TOKEN` 的顺序取 token，仓库里一个密钥都没配也能正常提交推送（走 `GITHUB_TOKEN` 时写权限由各自的 `permissions:` 声明，不依赖仓库全局的 Workflow permissions 设置）。用 `GITHUB_TOKEN` 推送不会产生新的 workflow 事件，正好杜绝自触发循环；若要用自己的令牌，建一个细粒度 PAT（只勾 **Contents: Read and write**，需要我用 API 代管密钥时再加 `Actions: Read and write`）填进 `ACTION_TOKEN`；注意令牌一旦填进来就会顶掉内置 `GITHUB_TOKEN`，**少了 contents: write 会直接 push 403**（已实测：只有 Actions 权限的令牌读写 workflow 正常，`git push` 返回 `Permission to ixmu/ros-cnip-rsc.git denied to ixmu`），过期同理，所以宁可留空让内置令牌兜底。`ROS CNIP List` 和 `NoRoute Config` 都在提交前有一步 `Check push credentials`：只打印本次用的是哪个凭据来源（不回显内容），并对该凭据做一次 `git push --dry-run` 权限探测，令牌权限不足或过期时先给出明确告警。

**运行记录**：GitHub 默认保留 90 天，日更工作流很快堆出几百条历史，`Clean Workflows` 把保留期收紧到 7 天（每个工作流另保底 3 条，进行中的运行永不动）。逻辑在 `.github/scripts/clean_runs.py`，直接调 REST API，不依赖第三方 action；定时任务每周执行一次，也可手动触发并临时调整保留天数、或先用 `dry_run` 看看会删掉哪些记录。三个工作流的依赖均已固定在 Node 24 运行时的大版本（`actions/checkout@v7`、`actions/setup-python@v7`、`stefanzweifel/git-auto-commit-action@v7`），无 Node 弃用告警。

### 两套产物

| 目录 | 定位 | IPv4 | IPv6 | 路由条数¹ | 中国IP覆盖率 v4 / v6 | 精确率 v4 / v6 | 单族下发体积² |
|------|------|-----:|-----:|---------:|:-------------------:|:-------------:|------------:|
| `ocserv/` | 标准档 | 1000 | 800 | 1008 / 804 | 98.73% / 100.00% | 99.65% / 99.96% | 48 KB / 40 KB |
| `ocserv/lite/` | 精简档（受限客户端） | 320 | 384 | 328 / 388 | 88.76% / 100.00% | 96.39% / 97.74% | 15 KB / 19 KB |

> ¹ 含文件末尾附带的 12 条本地/保留段（IPv4 8 条 + IPv6 4 条），这部分不计入条数预算。
> ² ocserv 把每条路由作为一行 `X-CSTP-Split-Exclude:` 下发，实测约 48~50 B/条。IPv4 与 IPv6 两张表按地址族分别引入、**不会同时加载**，所以条数预算和体积都按单族计算。

指标以全量列表 `all_china.rsc` / `all_china_v6.rsc` 为基准：

- **中国IP覆盖率**——列表里的中国 IP 有多少被 no-route 命中，低说明有国内流量白跑隧道（只是变慢，仍可用）；
- **精确率**——no-route 命中的地址里有多少确实是中国 IP，低说明有境外 IP 被误判直连（翻墙失效的主要原因，危害更大）；
- **超覆盖**——多包含的地址数量占中国 IP 总量的比例。

### 为什么是 1000 + 800（按族独立计算）

- **服务端没有条数上限**：`config.c` 对 `no-route` 只做语法检查、不限量，`send_routes()`（`worker-vpn.c`）逐条拼 `X-CSTP-Split-Exclude` 头。条目多只会线性增大下发体积，ocserv 老版本（0.4.x）与 1.x 最新版在这点上没有差别，客户端也不用担心 ocserv 版本。
- **客户端的上限是字节而不是条数**：Android 平台 VPN profile 的硬上限是 128 KB（AOSP `Vpn.java`：`MAX_VPN_PROFILE_SIZE_BYTES = 1 << 17`，超限直接报 `Profile too big`）。按实测约 50 B/条折算，单族 1000 条 ≈ 48 KB，连证书、DNS、域名一起也只用掉三分之一左右；即便把 v4、v6 两张表同时下发（约 88 KB）仍在限制内。Cisco AnyConnect / Secure Client 4.10 及更新版本（Windows、macOS、Linux）没有公布 split exclude 的固定条数上限，走的是同一条 `X-CSTP-Split-Exclude` 解析路径，4.10 能收的路由数不会比新版少；真正没保证的是移动端 App 处理大路由表的开销，所以另外提供 `ocserv/lite/`（约 330 / 390 条）。
- **再往上没有意义**：IPv4 覆盖率在 1000 条时已达 98.73%，λ=1 的精确率 99.65%，超过 1000 条后每 100 条只换 0.1~0.2 个点；IPv6 源列表只有 2088 条，800 条已把超覆盖压到 0.0%，继续加条只是把同一批地址拆得更碎。
- 精度收益的拐点也支持这个选择：IPv6 精确率从 320 条的 85.9% 跳到 384 条的 97.7%，此后每加 64 条只涨约 1 个点；IPv4 在 λ=1 下 512 → 800 → 1000 分别只多换 3.7、0.7 个点覆盖率。

### 算法

`.github/scripts/norange.py`：前缀树 + 动态规划。对树上每个节点求 `dp[k] = 用 k 条规则覆盖该子树的最小代价`，代价定义为

```
代价 = 超覆盖地址数 + λ × 被丢弃的中国地址数
```

每个节点有三种选择：整体折叠成 1 条前缀、在两个孩子子树之间分配 k 条、或整棵子树直接丢弃（用 0 条）。
所以条数是**硬上限**，算法可以选择放弃零碎小段，而不是用一条巨大的汇总段去包它——这正是准确率的来源。

默认 `λ = 1`。标准档 1000 条里被丢弃的最大块只有 /19（8,192 个地址），合计 3,609,600 IP = 中国 IP 的 1.27%，其中 996 条是 ≤/24 的零碎段、合计仅 254,976 IP；被裁掉的零星小段（`1.118.64.0/19`、`8.150.0.0/19`、`27.98.224.0/19` 一类）多是云机房段，走隧道通常反而更合理。
同条数不裁剪（λ=0）时精确率只有 55.27%，λ=1 把它拉到 99.65%。
精简档 320 条时最大丢弃段升到 /15，裁剪比例 11.24%，换到 96.39% 的精确率。

λ 越大越保守（少裁剪、覆盖率高、精确率低）；`λ = 0` 关闭裁剪，必然 100% 覆盖。IPv6 源列表本身足够紧凑，两套都固定 `λ = 0`。

### 条数 × λ 实测对照（IPv4，格式：中国IP覆盖率 / 精确率）

| 目标条数 | 256 | 320 | 448 | 512 | 640 | 800 | **1000** |
|---------:|:---:|:---:|:---:|:---:|:---:|:---:|:------:|
| λ=1 | 86.60 / 94.95 | 88.76 / 96.39 | 93.00 / 97.54 | 94.38 / 97.67 | 96.64 / 98.41 | 98.03 / 99.17 | **98.73 / 99.65** |
| λ=2 | 90.93 / 89.21 | 93.23 / 90.57 | 95.20 / 94.21 | 96.49 / 94.63 | 97.67 / 96.94 | 98.49 / 98.50 | 99.07 / 99.12 |
| λ=4 | 95.51 / 79.63 | 95.69 / 85.48 | 97.89 / 88.06 | 98.07 / 91.24 | 98.67 / 94.33 | 99.00 / 97.08 | 99.33 / 98.43 |

IPv6（`λ = 0`，覆盖率恒为 100%）：

| 目标条数 | 256 | 320 | **384** | 448 | 512 | 640 | **800** |
|---------:|:---:|:---:|:-----:|:---:|:---:|:---:|:-----:|
| 精确率 | 35.16% | 85.94% | **97.74%** | 98.75% | 99.24% | 99.76% | **99.96%** |
| 超覆盖 | 184% | 16.4% | 2.3% | 1.3% | 0.8% | 0.2% | 0.0% |

### 与手工 NoRoute 列表对比

对比对象：`ixmu/Note` 仓库 `Ocserv/ocserv/config-per-group/NoRoute`（198 条，按 /11 粒度手工汇总，不含本地段）。

| 方案 | 条数 | 中国IP覆盖率 | 精确率 |
|------|-----:|-------------:|-------:|
| 手工 NoRoute 列表 | 198 | 95.19% | 43.87% |
| 本算法 λ=1 | 198 | 83.08% | **92.87%** |
| 本算法 λ=2 | 198 | 88.86% | 85.75% |
| 本算法 λ=4 | 198 | 93.53% | 77.12% |
| 本算法精简档 λ=1 | 320 | 88.76% | 96.39% |
| 本算法标准档 λ=1 | 1000 | **98.73%** | **99.65%** |

手工列表用大段汇总换覆盖率，精确率仅 43.87%——过半境外 IP 会被判成直连。相同条数下本算法可做到 92.87% 精确率；若也要覆盖它 95.19% 的中国 IP，取 λ=4 只要 320 条（95.69% / 85.48%），而标准档在精确率上高出近 56 个百分点。

### 格式与使用

默认输出 CIDR 写法，IPv4 / IPv6 一致：

```ini
# IPv4
no-route = 1.12.0.0/14
# IPv6
no-route = 2001:250::/30
```

ocserv 的 route/no-route 只接受 `地址/前缀` 或 `地址/点分掩码` 两种写法（空格分隔的掩码会被判非法并丢弃）。两种写法解析后的路由集合完全相同，对准确率没有影响，CIDR 只带来两点实际好处：文件小 26%，以及可直接复制到 iptables / ipset / nftables / RouterOS。上游解析代码 `src/ip-util.c`（master 的 `ip_route_sanity_check()`、1.3.0 的 `ipv4_network_to_strmask()`）都会把数字前缀在内部转换成点分掩码，因此 ocserv 4.10 这类老版本同样可用。需要点分掩码时加 `--ipv4-format netmask`。

标准用法——按地址族分别引入标准档：

```ini
include = /etc/ocserv/no-route-ipv4.conf
include = /etc/ocserv/no-route-ipv6.conf
```

老客户端 / 移动端分组改用精简档：`config-per-group` 里的 `no-route` 默认**替换**全局值，需要与全局叠加时把 `append-routes = true` 打开。

```ini
# /etc/ocserv/config-per-group/mobile   （内容取自 ocserv/lite/ 两个文件）
no-route = 1.12.0.0/14
...
```

文件末尾附带的本地/保留段（`10/8`、`100.64/10`、`127/8`、`169.254/16`、`172.16/12`、`192.168/16`、`224/4`、`240/4`，IPv6 为 `::1/128`、`fc00::/7`、`fe80::/10`、`ff00::/8`）不计入条数预算，用 `--no-include-private` 可关闭，且已验证与中国规则无重叠。

本地重新生成：

```bash
# 标准档（等于默认参数）
python3 .github/scripts/norange.py
# 精简档
python3 .github/scripts/norange.py --out-dir ocserv/lite \
    --target-v4 320 --target-v6 384 --prune-v4 1
# 单族使用（不需要另一族时直接关掉）
python3 .github/scripts/norange.py --target-v6 0
```

### 如何调参

no-route 误判（境外 IP 被直连）通常比漏命中（国内 IP 白跑隧道）更影响体验，因此默认取偏保守的 `λ = 1`。

- 某些境外站点直连了 → λ 调到 0~1，或降低条数；
- 国内流量偏多、隧道负载高 → λ 调到 2~4（1000 条 @λ=4 = 99.33% / 98.43%），覆盖率优先；
- 移动端 / 老客户端占比高 → 用 `ocserv/lite/`，或手动运行时把标准档压到 320~512 条；
- 只用 IPv4 → `--target-v6 0`，生成的 v6 文件只剩本地段。
