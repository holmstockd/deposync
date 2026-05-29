# -*- coding: utf-8 -*-
"""
Plain-text debug log so the user can trace exactly what the app is doing.

Always writes to  ~/DepoSync_debug.log  and, once a job's video folder is
known, ALSO writes  <video_dir>/DepoSync_debug.log  so the trace sits right
next to the deposition the user is working on.
"""
import os
import sys
import time
import traceback
from datetime import datetime

_paths = [os.path.join(os.path.expanduser('~'), 'DepoSync_debug.log')]
_t0 = time.time()


def add_path(directory: str) -> None:
    """Also log into a file in `directory` (e.g. the video folder)."""
    try:
        p = os.path.join(directory, 'DepoSync_debug.log')
        if p not in _paths:
            _paths.append(p)
            log(f'--- debug log attached to {p} ---')
    except Exception:
        pass


def log(msg: str) -> None:
    line = (f'[{datetime.now():%H:%M:%S}] '
            f'(+{time.time() - _t0:7.1f}s)  {msg}\n')
    for p in list(_paths):
        try:
            with open(p, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass
    try:
        sys.stderr.write(line)
    except Exception:
        pass


def exc(context: str) -> None:
    """Log the current exception with traceback."""
    log(f'ERROR in {context}:\n{traceback.format_exc()}')


def banner(msg: str) -> None:
    log('=' * 60)
    log(msg)
