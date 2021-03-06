# *-* coding: utf-8 *-*
"""Implements the lexibank cache. (forked from lingpy)

Some operations in lingpy may be time consuming, so we provide a mechanism to cache the
results of these operations.
"""
from __future__ import unicode_literals, print_function, absolute_import, division
import pickle

from clldutils.path import Path
from appdirs import user_cache_dir


DIR = Path(user_cache_dir('lexibank'))


def path(filename):
    return DIR.joinpath(Path(filename).name + '.pkl')


def load(filename):
    pt = path(filename)
    if not pt.exists():
        raise ValueError("File not found.")
    with path(filename).open('rb') as fp:
        return pickle.load(fp)


def dump(data, filename):
    if not DIR.exists():
        DIR.mkdir(parents=True)  # pragma: no cover
    with path(filename).open('wb') as fp:
        pickle.dump(data, fp)
