#!/usr/bin/env sh

# interface=(/sys/class/net/???*)
# interface=/sys/devices/pci0000:00/0000:00:1d.2/0000:3c:00.0/net/wlan0
# interface=/sys/devices/pci0000:00/0000:00:1d.0/0000:03:00.0/0000:04:02.0/0000:3b:00.0/usb4/4-1/4-1.1/4-1.1:1.0/net/enp59s0u1u1
# interface=/sys/class/net/wlan0
interface=/sys/class/net/enp0s31f6
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

        if [ "${mib_dec:1:2}" -ge 9 ]; then
            mib_dec="0"
            mib_int=$(( mib_int + 1))
        elif [ "${mib_dec:1:2}" -ge 5 ]; then
            mib_dec=$(( ${mib_dec:0:1} + 1 ))
        else
            mib_dec=$(( ${mib_dec:0:1} ))
        fi


        printf "%-69s" "<span size=\"10000\">${mib_int}.${mib_dec}</span><span weight=\"800\" foreground=\"#3584FF\" size=\"6000\">M</span>"
    else
        printf "%-69s" "<span size=\"10000\">$(printf "%3s" ${kib})</span><span weight=\"800\" size=\"6000\">K</span>"
    fi
}



while true; do
    read last_rx < "${interface}/statistics/rx_bytes"
    read last_tx < "${interface}/statistics/tx_bytes"
    sleep 1
    read rx < "${interface}/statistics/rx_bytes"
    read tx < "${interface}/statistics/tx_bytes"
    printf "↓$(readable $((rx - last_rx))) ↑$(readable $((tx - last_tx)))\n" || exit 1
done

