#!/usr/bin/env bash
set -euo pipefail

# step 2: create canvas with text
namestring="$1"
infostring="$2"
base_img="$3"
font="Inter-Regular"

face="$HOME/face.png"
canvasForName="$HOME/canvasForName.png"
canvasForInfo="$HOME/canvasForInfo.png"
circleblack="$HOME/circleblack.png"
blackCircleCanvas="$HOME/blackCircleCanvas.png"

# step 1: resize large, circular photo
convert -resize 277x277 "$base_img" "$face"

# First Name
convert -size 420x600 canvas:transparent -gravity Center -font "$font" -pointsize 48 -annotate +0+198 "$namestring" -blur 0x3 -annotate +1+200 "$namestring" -blur 0x3 -annotate -1+200 "$namestring" -blur 0x3 -annotate +0+200 "$namestring" -blur 0x3 -annotate +0+202 "$namestring" -blur 0x3 -fill white -annotate +0+200 "$namestring" "$canvasForName"

# then info
convert -size 420x600 canvas:transparent -gravity Center -font "$font" -pointsize 30 -annotate +0+254 "$infostring" -blur 0x3 -annotate +1+256 "$infostring" -blur 0x3 -annotate -1+256 "$infostring" -blur 0x3 -annotate +0+256 "$infostring" -blur 0x3 -annotate +0+258 "$infostring" -blur 0x3 -fill white -annotate +0+256 "$infostring" "$canvasForInfo"

convert "$canvasForName" "$canvasForInfo" -gravity center -composite  "$canvasForName"
rm "$canvasForInfo"

# step 3: create canvas with blag bg that should be blurred
convert -size 307x307 canvas:transparent -draw "circle 152.5,152.5 152.5,0"  "$circleblack"
convert -size 530x530 xc:transparent "$blackCircleCanvas"
convert "$blackCircleCanvas" "$circleblack" -gravity Center -composite "$blackCircleCanvas"
rm "$circleblack"

# step 4: blur it
convert "$blackCircleCanvas" -blur 0x8 "$blackCircleCanvas"

# step 5: set the blurred bg onto the canvas
convert "$canvasForName" "$blackCircleCanvas" -gravity center -composite  "$canvasForName"
rm "$blackCircleCanvas"

# Puts face on bg:
convert -colorspace sRGB "$canvasForName" "$face" -gravity center -composite "$canvasForName"
convert -gravity East -chop 5x0 "$canvasForName" .faceLock.png
rm "$canvasForName"
rm "$face"


# For making cirle crops
# convert picture.jpg \
#         -gravity Center \
#         \( -size 503x503 \
#         -geometry +70-280 \
#            xc:Black \
#            -fill White \
#            -draw 'circle 251 251 251 0' \
#            -alpha Copy \
#         \) -compose CopyOpacity -composite \
#         -trim .face.png


