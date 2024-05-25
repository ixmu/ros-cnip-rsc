#!/bin/bash

curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/all_china$(date -d "+%Y-%m-%d")-05.rsc > all_china.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/telecom$(date -d "+%Y-%m-%d")-05.rsc > telecom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/unicom$(date -d "+%Y-%m-%d")-05.rsc > unicom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/mobile$(date -d "+%Y-%m-%d")-05.rsc > mobile.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/cernet$(date -d "+%Y-%m-%d")-05.rsc > cernet.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/other$(date -d "+%Y-%m-%d")-05.rsc > other.rsc


curl -kLfsm 5 https://raw.githubusercontent.com/ChanthMiao/China-IPv6-List/release/cn6.txt | sed -e 's/^/add address=/' -e 's/$/ comment=\"\" disabled\=no list\=List_ALL_China/'>/tmp/all_china_v6.rsc
echo "/ipv6 firewall address-list" >all_china_v6.rsc
cat /tmp/all_china_v6.rsc >> all_china_v6.rsc
