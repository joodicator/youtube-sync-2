# youtube-sync-2
Maintain offline archives of the videos in certain YouTube playlists.

## Requirements
* [Python](http://python.org) 3
* [youtube-dl](//github.com/rg3/youtube-dl/)
* [google-api-python-client](//github.com/google/google-api-python-client)

## Usage
See the output of:
```bash
./sync.py --help
./check.py --help
```

## Automation
For regular use, it is recommended to write shell scripts that call `sync.py` and `check.py` with the appropriate arguments. For example, on Linux, replacing `PATH_TO_REPO`, `YOUR_EMAIL_ADDRESS`, `YOUR_2_LETTER_COUNTRY_CODE`, `YOUR_FAVOURITES_PLAYLIST_ID` and `YOUR_LIKED_VIDEOS_PLAYLIST_ID` with appropriate values:

```bash
#!/bin/bash
exec $(dirname $0)/PATH_TO_REPO/sync.py \
    -u YOUR_EMAIL_ADDRESS \
    --need-regions YOUR_2_LETTER_COUNTRY_CODE \
    "$@" \
    'https://www.youtube.com/playlist?list=YOUR_FAVOURITES_PLAYLIST_ID' \
    'https://www.youtube.com/playlist?list=YOUR_LIKED_VIDEOS_PLAYLIST_ID' \
    --format "bestvideo[height<=360]+bestaudio[abr<=128]/best[height<=360][abr<=128]/best[height<=360]" \
    --max-filesize 50M --all-subs --embed-subs --add-metadata
```

```bash
#!/bin/bash
exec $(dirname $0)/PATH_TO_REPO/check.py \
    -u YOUR_EMAIL_ADDRESS \
    --need-regions YOUR_2_LETTER_COUNTRY_CODE \
    --refresh playlists \
    'https://www.youtube.com/playlist?list=YOUR_FAVOURITES_PLAYLIST_ID' \
    'https://www.youtube.com/playlist?list=YOUR_LIKED_VIDEOS_PLAYLIST_ID' \
    "$@"
```

Moreover, any command-line flags in youtube-dl's system and user configuration files (`/etc/youtube-dl.conf` and `~/.config/youtube-dl/config`, or `%APPDATA%/youtube-dl/config.txt` on Windows) will be used by `sync.py` unless they are overridden on the actual command line.
