# ROS-cnip-script搬运自 www.tcp5.com 列表，加入ROS的导入命令制作而成。


>此列表仅包含IPV4地址，没有IPV6地址。

>自动修改为ROS命令脚本文件，不定期更新。

>加了一条在导入前清空名为“CNIP”列表的命令，避免出现新旧列表交叉冲突。

>加了一条导入列表时关闭日志输出的指令，避免日志刷屏。

>增加了10.0.0.0/8，172.16.0.0/12，192.168.0.0/16三个内网网段到CN列表，避免本地网络和VPN网络走标记路由。

附：ROS导入脚本

>请确保ROS网络可以正常访问github。

###### 在/System Script下添加如下脚本内容
```
/tool fetch url="https://fastraw.ixnic.net/ixmu/ros-cnip-rsc/main/all_china.rsc"
/system logging disable 0
/ip firewall address-list
remove [find list=List_ALL_China]
/import all_china.rsc
/system logging enable 0
:local List_ALL_China [:len [/ip firewall address-list find list="List_ALL_China"]]
/file remove [find name="cnip.rsc"]
:log info ("List_ALL_China列表更新:"."$List_ALL_China"."条规则")
```
建议手动执行，也可以在/System Scheduler下添加一个脚本定时
