# ROS-cnip-script搬运自 www.tcp5.com 列表，加入ROS的导入命令制作而成。


>此列表仅包含IPV4地址，没有IPV6地址。

>自动修改为ROS命令脚本文件，不定期更新。

>加了一条在导入前清空名为“CNIP”列表的命令，避免出现新旧列表交叉冲突。

>加了一条导入列表时关闭日志输出的指令，避免日志刷屏。


附：ROS导入脚本

>请确保ROS网络可以正常访问github。

###### 在/System Script下添加如下脚本内容
```
/tool fetch url="https://github.10105410.xyz/ixmu/ros-cnip-rsc/raw/refs/heads/main/all_china.rsc"
/system logging disable 0
/ip firewall address-list
remove [find list=List_ALL_China]
/import all_china.rsc
/system logging enable 0
/file remove [find name="all_china.rsc"]
:local ListAllChina [:len [/ip firewall address-list find list="List_ALL_China"]]
:log info ("List_ALL_China更新:"."$ListAllChina"."条")


/tool fetch url="https://github.10105410.xyz/ixmu/ros-cnip-rsc/raw/refs/heads/main/all_china_v6.rsc"
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
