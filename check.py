#!/usr/bin/env python3

import sys
import re
import os
import argparse

from youtube_dl.extractor.youtube import YoutubeIE
from youtube_dl.utils import ExtractorError

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import sync

#===============================================================================
arg_parser = argparse.ArgumentParser(
    description = 'Outputs a shell script to initialise a video archive by '
        'renaming any existing videos found under the local directory to '
        'include appropriate metadata. Also prints to stderr a detailed '
        'accounting of the archival status of all playlist entries and files.',
    parents = [sync.base_arg_parser])
arg_parser.add_argument(
    '--refresh', choices=('none', 'playlists', 'all'), default='playlists',
    help='bypass the local playlist and/or video metadata cache')

def main(args, cont):
    ydl_params = { 'logtostderr': True }
    sync.main(args, ydl_params=ydl_params, cont=cont)

def init(ydl, playlists, files, login, cache, args):
    u_files, gu_files, bu_files = [file.path for file in files], [], []
    m_videos, u_videos, bm_videos, bu_videos = [], [], [], []

    fresh_p = args.refresh in ('all', 'playlists')
    fresh_v = args.refresh in ('all',)

    for video in sync.iter_videos(
    ydl, playlists, cache, args, refresh=fresh_p, exclude_bad=False):
        bad = sync.video_is_bad(video)
        matching_files = []
        for file in files:
            if match_file_video(file.name, video):
                matching_files.append(file.path)
                if file.path in u_files:
                    u_files.remove(file.path)
        if matching_files:
            (bm_videos if bad else m_videos).append((video, matching_files))
        else:
            (bu_videos if bad else u_videos).append(video)

    sync.save_cache(cache)

    ie = None
    for file in list(u_files):
        match = re.search(
            r'\.(ex[:\.])?(?P<video_id>[\w-]{11})(\.[a-zA-Z0-9]+)?$', file)
        if not match: continue
        video_id = match.group('video_id')
        if ie is None: ie = YoutubeIE(ydl)
        video = video_by_id(ydl, video_id, cache, args, refresh=fresh_v, ie=ie)
        u_files.remove(file)
        (bu_files if sync.video_is_bad(video) else gu_files).append((file, video))

    print('\n=== %d listed video(s) online and archived: ===' % len(m_videos), file=sys.stderr)
    for video, files in m_videos:
        print_video_files(video, files)

    print('\n=== %d listed video(s) not online but archived: ===' % len(bm_videos), file=sys.stderr)
    for video, files in bm_videos:
        print_video_files(video, files)

    print('\n=== %d unlisted video(s) not online but archived: ===' % len(bu_files), file=sys.stderr)
    for file, video in bu_files:
        print_video_files(video, [file])

    print('\n=== %d unlisted video(s) online and archived: ===' % len(gu_files), file=sys.stderr)
    for file, video in gu_files:
        print_video_files(video, [file])

    print('\n=== %d listed video(s) online but not archived: ===' % len(u_videos), file=sys.stderr)
    for video in u_videos:
        sync.print_video(video)

    print('\n=== %d listed video(s) not online and not archived: ===' % len(bu_videos), file=sys.stderr)
    for video in bu_videos:
        sync.print_video(video)

    d_videos = [(v,fs) for (v,fs) in bm_videos + m_videos if len(fs) > 1]
    print('\n=== %d video(s) with multiple matching files: ===' % len(d_videos), file=sys.stderr)
    for video, files in d_videos:
        print_video_files(video, files)

    print('\n=== %d file(s) not matching any video: ===' % len(u_files), file=sys.stderr)
    for file in u_files:
        print_file(file)

def print_file(file):
    print(' File: %s' % file, file=sys.stderr)

def print_video_files(video, files):
    print(file=sys.stderr)
    sync.print_video(video)
    for file in files:
        print_file(file)
        print_rename_file(file, video)

def print_rename_file(file, video):
    vid = '.%s%s' % ('ex.' if sync.video_is_bad(video) else '', video['id'])
    if video['id'] in file:
        new_file = re.sub(
            r'[-_\.](?:ex[:\.])?%s' % re.escape(video['id']), vid, file)
    else:
        new_file = re.sub(r'((?:\.[^\.]*)?)$', r'%s\1' % vid, file)
    if new_file != file:
        print('mv %s \\' % shesc(file))
        print('   %s' % shesc(new_file))
        print()

def video_by_id(ydl, video_id, cache, args, refresh=False, ie=None):
    video_url = 'https://youtube.com/watch?v=%s' % video_id
    if not refresh and video_url in cache:
        video = cache[video_url]
    else:
        try:
            if ie is None: ie = YoutubeIE(ydl)
            video = ie.extract(video_url)
        except ExtractorError as e:
            video = {'id':video_id, 'title':repr(e), '_bad':True}
    video = sync.postproc_video(video, args)
    cache[video_url] = video
    return video

def match_file_video(name, video):
    if video['id'] in name: return True
    if sync.video_is_bad(video): return False
    rname = re.findall(r'\w+', re.sub(r'\.[^\.]+$', '', name.lower()))
    rtitle = re.findall(r'\w+', video['title'].lower())
    return ''.join(rname) == ''.join(rtitle)

def shesc(*args):
    return ' '.join(
        "'%s'" % arg.replace("'", "'\\''")
        for arg in args)

if __name__ == '__main__':
    try:
        main(args=arg_parser.parse_args(), cont=init)
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        sys.exit(1)
