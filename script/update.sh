#!/bin/sh

curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/all_china$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/all_china.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/telecom$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/telecom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/unicom$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/unicom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/mobile$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/mobile.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/cernet$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/cernet.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/other$(date -d "yesterday" "+%Y-%m-%d")-12.rsc > /tmp/other.rsc

cp -f cnip.rsc.defconfig all_chin && cat /tmp/all_china.rsc >> all_chin
touch telecom.rsc && cat /tmp/telecom.rsc >> telecom.rsc
touch unicom.rsc && cat /tmp/unicom.rsc >> unicom.rsc
touch mobile.rsc && cat /tmp/mobile.rsc >> mobile.rsc
touch cernet.rsc && cat /tmp/cernet.rsc >> cernet.rsc
touch other.rsc && cat /tmp/other.rsc >> other.rsc
