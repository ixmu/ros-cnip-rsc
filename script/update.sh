#!/bin/bash

update_ip () {
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/all_china$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/all_china.rsc
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/telecom$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/telecom.rsc
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/unicom$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/unicom.rsc
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/mobile$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/mobile.rsc
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/cernet$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/cernet.rsc
  curl -kLfsm 5 http://www.tcp5.com/list/$(date "+%Y.%m")/other$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc > /tmp/other.rsc
  cat /tmp/all_china.rsc > all_china.rsc
  cat /tmp/telecom.rsc > telecom.rsc
  cat /tmp/unicom.rsc > unicom.rsc
  cat /tmp/mobile.rsc > mobile.rsc
  cat /tmp/cernet.rsc > cernet.rsc
  cat /tmp/other.rsc > other.rsc
}
update_ip_v6 () {
  curl -kLfsm 5 https://raw.githubusercontent.com/ChanthMiao/China-IPv6-List/release/cn6.txt | sed -e 's/^/add address=/' -e 's/$/ comment=\"\" disabled\=no list\=List_ALL_China/'>/tmp/all_china_v6.rsc
  echo "/ipv6 firewall address-list" >all_china_v6.rsc
  cat /tmp/all_china_v6.rsc >> all_china_v6.rsc
}
hour=0
while true; do
  if [ "$hour" -gt 24 ]; then
    break
    exit 1
  fi

  status_code=$(curl -s -o /dev/null -w "%{http_code}" http://www.tcp5.com/list/$(date "+%Y.%m")/all_china$(date -d "yesterday" "+%Y-%m-%d")-${hour}.rsc)

  if [ "$status_code" -eq 200 ]; then
    update_ip
    update_ip_v6
    break
  else
    hour=$((hour + 1))
  fi
done



