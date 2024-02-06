#!/bin/bash

hour=0
timeout="2024-02-04"
# $(date -d "yesterday" "+%Y-%m-%d")
while true; do
  if [ "$hour" -gt 24 ]; then
    break
  fi

  status_code=$(curl -s -o /dev/null -w "%{http_code}" http://www.tcp5.com/list/$(date "+%Y.%m")/all_china${timeout}-${hour}.rsc)

  if [ "$status_code" -eq 200 ]; then
    break
  else
    hour=$((hour + 1))
  fi
done

if [ "$hour" -eq 25 ]; then
  exit 1
fi

curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/all_china${timeout}-${hour}.rsc > /tmp/all_china.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/telecom${timeout}-${hour}.rsc > /tmp/telecom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/unicom${timeout}-${hour}.rsc > /tmp/unicom.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/mobile${timeout}-${hour}.rsc > /tmp/mobile.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/cernet${timeout}-${hour}.rsc > /tmp/cernet.rsc
curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/other${timeout}-${hour}.rsc > /tmp/other.rsc

cat /tmp/all_china.rsc > all_china.rsc
cat /tmp/telecom.rsc > telecom.rsc
cat /tmp/unicom.rsc > unicom.rsc
cat /tmp/mobile.rsc > mobile.rsc
cat /tmp/cernet.rsc > cernet.rsc
cat /tmp/other.rsc > other.rsc

