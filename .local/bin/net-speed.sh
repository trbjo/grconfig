#!/usr/bin/env sh

interfaces=(/sys/class/net/???*)

for iface in ${interfaces[@]}; do
    case ${iface##*/} in
        tun**)
            interface=$iface
            break
            ;;
        enp**)
            interface=$iface
            break
            ;;
        wlan**)
            interface=$iface
            break
            ;;
        *)
            exit
            ;;
    esac
done

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



# while true; do
    read last_rx < "${interface}/statistics/rx_bytes"
    read last_tx < "${interface}/statistics/tx_bytes"
    sleep 1
    read rx < "${interface}/statistics/rx_bytes"
    read tx < "${interface}/statistics/tx_bytes"
    printf "↓$(readable $((rx - last_rx))) ↑$(readable $((tx - last_tx)))\n" || exit 1
# done

