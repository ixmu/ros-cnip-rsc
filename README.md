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

由 `.github/workflows/norange.yml` 在每次列表更新后自动生成，输出到 `ocserv/` 目录。

| 文件 | 条数 | 过覆盖率 |
|------|------|----------|
| `ocserv/no-route-ipv4.conf` | ≤ 1000 | ~24% |
| `ocserv/no-route-ipv6.conf` | ≤ 500 | ~0.8% |

**算法**：对原始 .rsc 列表进行 trie DP 最优 CIDR 聚合，在指定条数限制下最小化过覆盖（非中国 IP 被误加入 bypass 列表）。

**ocserv 格式**：
```ini
# IPv4: no-route = <网络地址> <点分掩码>
# IPv6: no-route = <IPv6地址>/<前缀长度>
```

在 ocserv.conf 中引入：
```ini
# 分路由：中国 IP 不走隧道
include = /path/to/no-route-ipv4.conf
include = /path/to/no-route-ipv6.conf
```

也可手动触发重新生成：**Actions → NoRoute Config → Run workflow**。
