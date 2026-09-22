#!/bin/sh
# Load environment variables
if [ -f "/root/armor-edge/.env" ]; then
    . /root/armor-edge/.env
else
    echo "Error: .env file not found"
    exit 1
fi

DEBIAN_IP="192.168.50.2"
MAC_IP="192.168.50.3"

get_context() {
    DATA=$(curl -s http://ip-api.com/json/)
    IP=$(echo $DATA | jsonfilter -e '$.query')
    ISP=$(echo $DATA | jsonfilter -e '$.isp')
    CITY=$(echo $DATA | jsonfilter -e '$.city')
    COUNTRY=$(echo $DATA | jsonfilter -e '$.country')
    LAT=$(echo $DATA | jsonfilter -e '$.lat')
    LON=$(echo $DATA | jsonfilter -e '$.lon')
    
    if [ -z "$IP" ]; then
        IP=$(curl -s https://ifconfig.me)
        ISP="Unknown"
        CITY="Unknown"
        LAT="0"
        LON="0"
    fi
    
    echo "Time: $(date +"%d/%m/%Y, %H:%M:%S")
ISP Location: $CITY, $COUNTRY (Data Exchange)
Coords: $LAT, $LON (https://maps.google.com/?q=$LAT,$LON)
IP: $IP · $ISP"
}

check_node() {
    IP=$1
    NAME=$2
    FLAG="/tmp/${NAME}_down"
    
    if [ -f "/tmp/${NAME}_paused" ]; then return; fi

    ping -c 2 -W 2 $IP > /dev/null
    if [ $? -ne 0 ]; then
        if [ ! -f "$FLAG" ]; then
            CONTEXT=$(get_context)
            MSG="🔴 $NAME is OFFLINE

$CONTEXT"
            curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
            -d chat_id="$TG_CHAT" \
            --data-urlencode "text=$MSG"
            touch "$FLAG"
        fi
    else
        if [ -f "$FLAG" ]; then
            CONTEXT=$(get_context)
            MSG="🟢 $NAME is BACK ONLINE

$CONTEXT"
            curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
            -d chat_id="$TG_CHAT" \
            --data-urlencode "text=$MSG"
            rm -f "$FLAG"
        fi
    fi
}

check_node $DEBIAN_IP "psth1"
check_node $MAC_IP "pstt1"
