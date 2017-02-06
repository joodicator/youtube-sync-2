#!/usr/bin/env python3

from functools import *
from itertools import *
import sys
import os
import re
import argparse
import getpass
import pickle

import youtube_dl.options
from youtube_dl import YoutubeDL
from youtube_dl.extractor.youtube import YoutubePlaylistIE

import ytdata

CACHE_FILE = '.youtube-sync-cache'
ytservice = ytdata.build_service()

#===============================================================================
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'rb') as file:
            return pickle.load(file)
    else:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, 'wb') as file:
        pickle.dump(cache, file)

#===============================================================================
base_arg_parser = argparse.ArgumentParser(add_help=False)
base_arg_parser.add_argument(
    '-u', '--username', dest='username',
    help='YouTube login name')
base_arg_parser.add_argument(
    '-p', '--password', dest='password',
    help='YouTube password')
base_arg_parser.add_argument(
    '--need-regions', metavar='RC[,RC[...]]', dest='need_regions', default='',
    help='comma-separated list of required region codes.')
base_arg_parser.add_argument(
    '--exclude-file', metavar='PATH', dest='exclude_files', action='append',
    help='file or directory to exclude from the search for existing videos.')
base_arg_parser.add_argument(
    'playlists', nargs='+', metavar='PLAYLIST',
    help='URL of a playlist whose videos are to be archived')

arg_parser = argparse.ArgumentParser(
    description = 'Synchronises a video archive by downloading any videos in '
        'the given playlists not present under the current directory. '
        'Archived video filenames must end with the video ID, optionally '
        'followed by a file extension. Newly downloaded videos are placed new/.',
    parents = [base_arg_parser])
arg_parser.add_argument(
    '--refresh', choices=('none', 'playlists'), default='playlists',
    help='control usage of the local playlist cache')
arg_parser.add_argument(
    'ydl_args', nargs=argparse.REMAINDER, metavar='...',
    help='arguments to be passed to youtube-dl')

def get_args(args):
    if args.username is None:
        login = None
    elif args.password is None:
        password = getpass.getpass('Enter password for %s: ' % args.username)
        login = (args.username, password)
    else:
        login = (args.username, args.password)
    return login, args

def main(args, ydl_params=None, cont=tuple):
    login, args = get_args(args)

    if ydl_params is None:
        ydl_params = {}
    if login is not None:
        ydl_params['username'], ydl_params['password'] = login
    ydl = YoutubeDL(ydl_params)

    exclude_re = re.compile('(%s)$' % '|'.join(
        r'(%s)(/.*)?' % re.escape(os.path.normpath(file))
        for file in args.exclude_files))
    files = [
        f for f in scandir_r()
        if not exclude_re.match(os.path.normpath(f.path))]
   
    cache = load_cache()
    result = cont(ydl, args.playlists, files, login, cache, args)

    return result

def sync(ydl, playlists, files, login, cache, args):
    dl_videos = []
    fresh_p = args.refresh != 'none'
    for video in iter_videos(ydl, playlists, cache, args, refresh=fresh_p):
        if not any(match_file_video(f, video) for f in files):
            dl_videos.append(video)
    if not dl_videos:
        print('\nNo videos to download.', file=sys.stderr)
        return

    save_cache(cache)

    print('Downloading %d videos.' % len(dl_videos))
    argv = []
    if login is not None and login[1] != '':
        argv += ['--username', login[0]]
        argv += ['--password', login[1]]
    argv += ['--output', 'new/%(title)s.%(id)s.%(ext)s']
    argv += ['--max-filesize', '100M']
    argv += ['--ignore-errors']
    argv += args.ydl_args
    argv += ['https://youtu.be/%s' % v['id'] for v in dl_videos]

    try:
        youtube_dl.main(argv)
    finally:
        files = list(scandir_r())
        failed_videos = []
        for video in dl_videos:
            v_files = [f for f in files if match_file_video(f, video)]
            if not v_files or any(file_is_incomplete(f, video) for f in v_files):
                failed_videos.append(video)
    
        if failed_videos:
            print('\nThe following %d videos (of %d) failed to download:'
                % (len(failed_videos), len(dl_videos)), file=sys.stderr)
            for video in failed_videos:
                print_video(video)
        else:
            print('\nAll %d videos successfully downloaded.'
                % len(dl_videos), file=sys.stderr)

def match_file_video(file, video):
    match = re.search(r'(^|\.)%s(\.|$)' % re.escape(video['id']), file.name)
    return match is not None

def file_is_incomplete(file, video):
    match = re.search(r'%s\.f\d+\.' % re.escape(video['id']), file.name)
    return match is not None

def iter_videos(ydl, playlists, cache, args, refresh=False, **kwds):
    memo, seen = dict(), set()
    for playlist_url in playlists:
        if not refresh and playlist_url in cache:
            videos = cache[playlist_url]
        else:
            videos = _iter_videos(ydl, playlist_url, args, memo, **kwds)
        new_videos = []
        for video in videos:
            video = postproc_video(video, args)
            if video['id'] not in seen:
                seen.add(video['id'])
                yield video
            new_videos.append(video)
        cache[playlist_url] = new_videos

def _iter_videos(ydl, playlist_url, args, memo=None, exclude_bad=True):
    playlist_ie = YoutubePlaylistIE(ydl)
    playlist = playlist_ie.extract(playlist_url)
    assert playlist['_type'] == 'playlist'

    playlist_info = dict(playlist)
    del playlist_info['entries']

    for video, index in zip(playlist['entries'], count()):
        assert video['_type'] == 'url'
        if memo is not None and video['id'] in memo:
            video = dict(memo[video['id']])
        elif exclude_bad and video_is_bad(video):
            continue
        else:
            video = postproc_video(video, args)
            if memo is not None:
                memo[video['id']] = video
        video['_playlist'] = playlist_info
        video['_index'] = index
        yield video

def postproc_video(video, args):
    if video.get('_postproc', 0) >= 5: return video
    video = dict(video)
    video['_postproc'] = 5

    part = 'snippet'        if video_is_bad(video) and '_error' not in video \
      else 'contentDetails' if args.need_regions \
      else ''
    if not part: return video

    results = ytservice.videos().list(
        id=video['id'], part=part
    ).execute()['items']
    if not results: return video

    info = results[0]
    if video_is_bad(video) and '_error' not in video:
        video['_error'] = video['title']
        video['title'] = info['snippet']['title']
        video['_bad'] = True
    elif args.need_regions:
        blocked = info.get('contentDetails', {}) \
                      .get('regionRestriction', {}).get('blocked', [])
        blocked_needed = [
            r for r in args.need_regions.upper().split(',') if r in blocked]
        if blocked_needed:
            if len(blocked) < max(len(blocked_needed), 10):
                blocked_in = ','.join(blocked)
            else:
                blocked_in = '%d regions including %s' % (
                    len(blocked), ','.join(blocked_needed))
            video['_error'] = '[Blocked in %s]' % blocked_in
            video['_bad'] = True

    return video

def video_is_bad(video):
    return re.match(r'\[(Deleted|Private) video\]$', video['title'], flags=re.I) \
        or video.get('_bad', False)

def print_video(video):
    print('Video: %s, %s%s%s' % (
        video['id'],
        '%s#%03d, ' % (video['_playlist']['title'][:3], video['_index']+1)
            if '_playlist' in video else '',
        '%s, ' % video['_error'] if '_error' in video else '',
        video['title'],
    ), file=sys.stderr)

def scandir_r(*args, **kwds):
    for entry in os.scandir(*args, **kwds):
        if entry.is_file():
            yield entry
        elif entry.is_dir():
            yield from scandir_r(entry.path)

if __name__ == '__main__':
    try:
        main(args=arg_parser.parse_args(), cont=sync)
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        sys.exit(1)
