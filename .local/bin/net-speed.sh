#!/usr/bin/env sh

# interface=(/sys/class/net/???*)
# interface=/sys/devices/pci0000:00/0000:00:1d.2/0000:3c:00.0/net/wlan0
# interface=/sys/devices/pci0000:00/0000:00:1d.0/0000:03:00.0/0000:04:02.0/0000:3b:00.0/usb4/4-1/4-1.1/4-1.1:1.0/net/enp59s0u1u1
interface=/sys/class/net/wlan0
# interface=/sys/devices/virtual/net/tun0

readable() {
    local bytes=$1
    local kib=$(( bytes >> 10 ))
    if [ $kib -lt 0 ]; then
        printf "? K"
    elif [ $kib -gt 1024 ]; then
        local mib_int=$(( kib >> 10 ))
        local mib_dec=$(( kib % 1024 * 976 / 10000 ))
        if [ "$mib_dec" -lt 10 ]; then
            mib_dec="0${mib_dec}"
        fi
        printf "${mib_int}.${mib_dec}<span size='7000'> Mb/s</span>"
    else
        printf "${kib}<span size='7000'> Kb/s</span>"
        # printf "%.2f<span size='7400'> Kb/s</span>" ${kib}
    fi
}

while true; do
    read last_rx < "${interface}/statistics/rx_bytes"
    read last_tx < "${interface}/statistics/tx_bytes"
    sleep 1
    read rx < "${interface}/statistics/rx_bytes"
    read tx < "${interface}/statistics/tx_bytes"
    printf "↓$(readable $((rx - last_rx)))   ↑$(readable $((tx - last_tx)))\n" || exit 1
done

