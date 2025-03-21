#!/bin/bash
ip route add 10.0.0.0/16 via 10.1.0.2 dev eth0

echo "$INSECURENET_HOST_IP insec" >> /etc/hosts
echo "$SECURENET_HOST_IP sec" >> /etc/hosts


sysctl net.ipv4.ip_forward=0
sysctl -p

#systemctl start nftables.service

#ip link set dev eth0 down
#ip link set dev eth0 address 02:42:0A:01:00:15
#ip link set dev eth0 up


ethtool --offload eth0 tx off
nft add table input_table 
nft 'add chain input_table input {type filter hook input priority -300;}'
nft 'add rule input_table input ip protocol udp udp checksum set 0'


while true; 
    do sleep 0.01;
    done