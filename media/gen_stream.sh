ffmpeg \
    -y \
    -re \
    -stream_loop -1 \
    -i $1.mp4 \
    -c:v libx264 -crf 21 -preset veryfast -g 25 -sc_threshold 0 \
    -c:a aac -b:a 128k -ac 2 \
    -f hls -hls_time 4 -hls_list_size 3 -hls_flags independent_segments+delete_segments -hls_base_url https://localhost:2015/$1/ \
    -streaming 1 -remove_at_exit 1 $1/stream.m3u8