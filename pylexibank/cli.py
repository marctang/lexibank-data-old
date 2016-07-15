"""
Main command line interface of the pylexibank package.

Like programs such as git, this cli splits its functionality into sub-commands
(see e.g. https://docs.python.org/2/library/argparse.html#sub-commands).
The rationale behind this is that while a lot of different tasks may be
triggered using this cli, most of them require common configuration.

The basic invocation looks like

    lexibank [OPTIONS] <command> [args]

"""
from __future__ import unicode_literals
import os
import sys
from time import time

from clldutils.clilib import ArgumentParser, ParserError
from clldutils.path import Path
from pycldf.dataset import Dataset as CldfDataset
from pycldf.util import MD_SUFFIX

import pylexibank
from pylexibank.util import data_path, formatted_number
from pylexibank.dataset import Dataset


HOME = Path(os.path.expanduser('~'))


class ValidationError(ValueError):
    def __init__(self, msg):
        self.msg = msg
        ValueError.__init__(self, msg)


def create(args):
    """Creates a new empty questionaire for a language specified by glottocode.

    lexibank create GLOTTOCODE [SOURCE]
    """
    pass


def is_dataset_dir(d):
    return d.exists() and d.is_dir() \
        and d.name != '_template' and d.joinpath('metadata.json').exists()


def get_dataset(args, name=None):
    name = name or args.args[0]
    dir_ = Path(name)
    if not is_dataset_dir(dir_):
        dir_ = data_path(name, repos=args.lexibank_repos)
        if not is_dataset_dir(dir_):
            raise ParserError('invalid dataset spec')
    return Dataset(dir_)


def download(args):
    """
    Download the raw data for a dataset.

    lexibank download DATASET_ID
    """
    get_dataset(args).download()


def list(args):
    for d in data_path(repos=Path(args.lexibank_repos)).iterdir():
        if is_dataset_dir(d):
            ds = Dataset(d)
            print(d.name, ds.md['dc:title'])


def with_dataset(args, func):
    if args.args:
        func(get_dataset(args), **vars(args))
    else:
        for d in data_path(repos=args.lexibank_repos).iterdir():
            if d.is_dir() and d.name != '_template' \
                    and d.joinpath('metadata.json').exists():
                s = time()
                print('processing %s ...' % d.name)
                func(get_dataset(args, d.name), **vars(args))
                print('... done [%.1f secs]' % (time() - s,))


def cldf(args):
    """
    Create CLDF datasets from the raw data for a dataset.

    lexibank cldf [DATASET_ID]
    """
    def _cldf(ds, **kw):
        ds.cldf(**kw)
        ds.write_cognates()

    with_dataset(args, _cldf)


def get_badge(words, name, prop=None):
    prop = prop or name
    if words:
        ratio = len([w for w in words if w.get(prop)]) / float(len(words))
    else:
        ratio = 1.0
    if ratio >= 0.99:
        color = 'brightgreen'
    elif ratio >= 0.9:
        color = 'green'
    elif ratio >= 0.8:
        color = 'yellowgreen'
    elif ratio >= 0.7:
        color = 'yellow'
    elif ratio >= 0.6:
        color = 'orange'
    else:
        color = 'red'
    ratio = int(round(ratio * 100))
    return badge(
        "{0}: {1}%".format(name, ratio), name, '%s%%25' % ratio, color
    )


def badge(title, name, value, color):
    return '![{0}](https://img.shields.io/badge/{1}-{2}-{3}.svg "{0}")'.format(
        title, name, value, color)


def readme(args):
    """Create a README.md file listing the contents of a dataset

    lexibank readme [DATASET_ID]
    """
    with_dataset(args, _readme)


def _readme(ds, **kw):
    lines = [
        '## %s' % ds.md.get('dc:title'),
        '',
        'Cite the source dataset as',
        '',
        '> %s' % ds.md.get('dc:bibliographicCitation'),
        '']

    if ds.md.get('dc:license'):
        lines.extend([
            'This dataset is licensed under a %s license' % ds.md.get('dc:license'),
            ''])

    if ds.md.get('dc:identifier'):
        lines.extend([
            'Available online at %s' % ds.md.get('dc:identifier'),
            ''])

    if ds.md.get('dc:related'):
        lines.extend([
            'See also %s' % ds.md.get('dc:related'),
            ''])

    lines.extend([
        '### Cognate sets',
        '%s cognates in %s cognate sets' % tuple(
            map(formatted_number, ds.cognate_stats())),
        '',
        '### Lexemes',
        '',
        ' | '.join(['Name', 'Languages', 'Concepts', 'Lexemes', 'Quality']),
        '|'.join([':--- ', ' ---:', ' ---:', ' ---:', ':---:']),
    ])

    totals = ['**total:**', set(), set(), 0, '']

    dslines = []
    for meta in sorted(ds.cldf_dir.glob('*' + MD_SUFFIX), key=lambda m: m.name):
        cldfds = CldfDataset.from_metadata(meta)

        badges = [
            get_badge(cldfds.rows, 'Glottolog', 'Language_ID'),
            get_badge(cldfds.rows, 'Concepticon', 'Parameter_ID'),
            get_badge(cldfds.rows, 'Source'),
        ]
        stats = cldfds.stats
        langs = len(stats['languages'])
        params = len(stats['parameters'])
        totals[1] = totals[1].union(stats['languages'])
        totals[2] = totals[2].union(stats['parameters'])
        totals[3] += len(cldfds)

        dslines.append(' | '.join([
            '[%s](%s)' % (cldfds.name, 'cldf/%s' % meta.name[:-len(MD_SUFFIX)]),
            '%s' % langs,
            '%s' % params,
            '%s' % len(cldfds),
            ' '.join(badges)]))

    for i in range(1, 4):
        totals[i] = formatted_number(totals[i])

    with ds.dir.joinpath('README.md').open('w', encoding='utf8') as fp:
        fp.write('\n'.join(lines + [' | '.join(totals)] + dslines))
    print(ds.dir.joinpath('README.md'))


def check(args):
    """Checks questionaires for completeness and validity.

    lexibank check [GLOTTOCODE]*

    If no GLOTTOCODEs are specified, all questionaires are checked.
    """
    pass


def main():
    parser = ArgumentParser('pylexibank', readme, download, cldf, list)
    parser.add_argument(
        '--lexibank-repos',
        help="path to lexibank data repository",
        default=Path(pylexibank.__file__).parent.parent)
    parser.add_argument(
        '--glottolog-repos',
        help="path to glottolog data repository",
        default=HOME.joinpath('venvs', 'glottolog3', 'glottolog'))
    parser.add_argument(
        '--concepticon-repos',
        help="path to concepticon data repository",
        default=HOME.joinpath('venvs', 'concepticon', 'concepticon-data'))
    sys.exit(parser.main())