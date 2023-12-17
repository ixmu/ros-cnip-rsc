#!/bin/sh

curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/all_china$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/all_china.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/telecom$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/telecom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/unicom$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/unicom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/mobile$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/mobile.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/cernet$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/cernet.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/other$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/other.rsc

cat ./script/cnip.rsc.defconfig /tmp/all_china.rsc > all_china.rsc
cat /tmp/telecom.rsc > telecom.rsc
cat /tmp/unicom.rsc > unicom.rsc
cat /tmp/mobile.rsc > mobile.rsc
cat /tmp/cernet.rsc > cernet.rsc
cat /tmp/other.rsc > other.rsc
