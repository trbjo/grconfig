#!/usr/bin/env bash

TORRENTLIST=$(transmission-remote -l | grep 'Finished')
notify-send.sh "Transmission" "<b>$(transmission-remote -l | perl -lne 'print $1 if /Finished(.*)/' | sed -e 's/^[ \t]*//')</b> finished" -t 20000 --icon="com.github.davidmhewitt.torrential" --default-action="nemo /home/tb/Downloads"

while read -r line; do
    TORRENTID=${line:0:4}
    transmission-remote localhost -t $TORRENTID -r  > /dev/null 2>&1
done <<< "$TORRENTLIST"


# # we try and clean up the newly downloaded files
# newest_file="$(exa --color=never --sort newest ~/Downloads  | tail -n 1)"
# newest_file_with_path="/home/tb/Downloads/$newest_file"
# if [ -f "$newest_file_with_path" ]; then
#     case "${newest_file_with_path##*.}" in
#          mp4|mkv|avi)
#             mv "$newest_file_with_path" /home/tb/Videos/
#             notify-send.sh "Transmission" "Moved $newest_file to Videos" --icon="com.github.davidmhewitt.torrential"
#             ;;
#         *)
#             exec /usr/bin/subl "$@"
#             ;;
#      esac

# else
#     fd . "$newest_file_with_path" -e txt -e nfo -e jpg -e sfv -X rm
#     fd "sample" "$newest_file_with_path" -X rm -rf

#     valuable_content=$(fd . "$newest_file_with_path" --exact-depth 1 --type f -e .mp4 -e .mkv -e .srt | wc -l)
#     num_of_files=$(ls -1q "$newest_file_with_path" | wc -l)

#     if [ $num_of_files -eq 1 ]; then
#         mv "$newest_file_with_path/$(ls -1q $newest_file_with_path)" /home/tb/Videos
#         rmdir "$newest_file_with_path"
#         notify-send.sh "Moved $newest_file to Videos"
#     elif [ "$num_of_files" == "$valuable_content" ]; then
#         mv "$newest_file_with_path" /home/tb/Videos
#         notify-send.sh "Moved $newest_file to Videos"
#     fi
# fi

mpv /usr/share/sounds/freedesktop/stereo/complete.oga
if [ "$(transmission-remote -l | wc -l)" -eq 2 ]; then
    systemctl --user stop transmission.service
fi
