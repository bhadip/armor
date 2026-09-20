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

check_node() {
    IP=$1
    NAME=$2
    FLAG="/tmp/${NAME}_down"
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    
    if [ -f "/tmp/${NAME}_paused" ]; then return; fi

    ping -c 2 -W 2 $IP > /dev/null
    if [ $? -ne 0 ]; then
        if [ ! -f "$FLAG" ]; then
            MSG="🔴 $NAME is OFFLINE
Time: $TIMESTAMP"
            curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
            -d chat_id="$TG_CHAT" \
            --data-urlencode "text=$MSG"
            touch "$FLAG"
        fi
    else
        if [ -f "$FLAG" ]; then
            MSG="🟢 $NAME is BACK ONLINE
Time: $TIMESTAMP"
            curl -s -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage" \
            -d chat_id="$TG_CHAT" \
            --data-urlencode "text=$MSG"
            rm -f "$FLAG"
        fi
    fi
}

check_node $DEBIAN_IP "psth1"
check_node $MAC_IP "pstt1"
