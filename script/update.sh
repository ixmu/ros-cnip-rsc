#!/bin/bash

# 年.月
path=$(date "+%Y.%m")
filename=$(date "+%Y-%m-%d")

status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://ros.tcp5.com/list/${path}/all_china${filename}-05.rsc")

if [ $status_code -ne 200 ]; then
    echo "非 200 状态码，退出程序"
    exit 1
fi

curl -kLfsm 5 http://ros.tcp5.com/list/${path}/all_china${filename}-05.rsc > all_china.rsc
curl -kLfsm 5 http://ros.tcp5.com/list/${path}/telecom${filename}-05.rsc > telecom.rsc
curl -kLfsm 5 http://ros.tcp5.com/list/${path}/unicom${filename}-05.rsc > unicom.rsc
curl -kLfsm 5 http://ros.tcp5.com/list/${path}/mobile${filename}-05.rsc > mobile.rsc
curl -kLfsm 5 http://ros.tcp5.com/list/${path}/cernet${filename}-05.rsc > cernet.rsc
curl -kLfsm 5 http://ros.tcp5.com/list/${path}/other${filename}-05.rsc > other.rsc


curl -kLfsm 5 https://raw.githubusercontent.com/ChanthMiao/China-IPv6-List/release/cn6.txt | sed -e 's/^/add address=/' -e 's/$/ comment=\"\" disabled\=no list\=List_ALL_China/'>/tmp/all_china_v6.rsc
echo "/ipv6 firewall address-list" >all_china_v6.rsc
cat /tmp/all_china_v6.rsc >> all_china_v6.rsc
