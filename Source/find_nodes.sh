#!/bin/bash
ip=$(hostname -I | awk '{print $2}')
echo $ip
baseip=$(echo $ip | cut -d"." -f1-3)
echo $baseip
for ip in $baseip.{1..254}; do
	ping -c 1 -W 1 $ip | grep "64 bytes" &
done
sleep 15
sudo arp -a

