"""
Main command line interface of the pylexibank package.

Like programs such as git, this cli splits its functionality into sub-commands
(see e.g. https://docs.python.org/2/library/argparse.html#sub-commands).
The rationale behind this is that while a lot of different tasks may be
triggered using this cli, most of them require common configuration.

The basic invocation looks like

    lexibank [OPTIONS] <command> [args]

"""
from __future__ import unicode_literals, division
import os
import sys
from time import time

from clldutils.clilib import ArgumentParser, ParserError
from clldutils.path import Path

import pylexibank
from pylexibank.util import data_path, formatted_number
from pylexibank.dataset import Dataset, synonymy_index, TranscriptionReport


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


def list_(args):
    for d in data_path(repos=Path(args.lexibank_repos)).iterdir():
        if is_dataset_dir(d):
            ds = Dataset(d)
            print(d.name, ds.md['dc:title'])


def with_dataset(args, func):
    if args.args:
        func(get_dataset(args), **vars(args))
    else:
        for d in sorted(
                data_path(repos=args.lexibank_repos).iterdir(), key=lambda d: d.name):
            if d.is_dir() and d.name != '_template' \
                    and d.joinpath('metadata.json').exists():
                s = time()
                print('processing %s ...' % d.name)
                try:
                    func(get_dataset(args, d.name), **vars(args))
                except NotImplementedError:
                    print('--not implemented--')
                print('... done %s [%.1f secs]' % (d.name, time() - s))


def report(args):
    """
    """
    def _report(ds, **kw):
        ds.report()

    with_dataset(args, _report)


def cldf(args):
    """
    Create CLDF datasets from the raw data for a dataset.

    lexibank cldf [DATASET_ID]
    """
    def _cldf(ds, **kw):
        ds.cldf(**kw)
        ds.write_cognates()

    with_dataset(args, _cldf)


def get_badge(words, name, prop=None, ratio=None):
    prop = prop or name
    if words:
        ratio = len([w for w in words if w.get(prop)]) / float(len(words))
    elif ratio:
        pass
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
    #
    # FIXME: write only summary into README.md
    # in case of multiple cldf datasets:
    # - separate lexemes.md and transcriptions.md
    #
    if not list(ds.cldf_dir.glob('*.csv')):
        return
    lines = [
        '# %s' % ds.md.get('dc:title'),
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

    lexlines = [
        '# %s - Lexemes per CLDF dataset\n' % ds.md.get('dc:title'),
        ' | '.join(['Name', 'Languages', 'Concepts', 'Lexemes', 'Synonymy', 'Quality']),
        '|'.join([':--- ', ' ---:', ' ---:', ' ---:', ' ---:', ':---:']),
    ]
    trlines = []
    rows = []

    totals = [set(), set(), 0, (0, 0)]

    for cldfds in ds.iter_cldf_datasets():
        rows.extend(cldfds.rows)
        badges = [
            get_badge(cldfds.rows, 'Glottolog', 'Language_ID'),
            get_badge(cldfds.rows, 'Concepticon', 'Parameter_ID'),
            get_badge(cldfds.rows, 'Source'),
        ]
        stats = cldfds.stats
        params = len(stats['parameters'])
        sindex, langs = synonymy_index(cldfds)
        if langs:
            sindex /= float(len(langs))
        else:
            sindex = 0
        totals[0] = totals[0].union(langs)
        totals[1] = totals[1].union(stats['parameters'])
        totals[2] += len(cldfds)
        totals[3] = (totals[3][0] + sindex, totals[3][1] + 1)

        lexlines.append(' | '.join([
            '[%s](%s)' % (cldfds.name, 'cldf/%s.csv' % cldfds.name),
            '%s' % len(langs),
            '%s' % params,
            '%s' % len(cldfds),
            '%.2f' % sindex,
            ' '.join(badges)]))

    tr = TranscriptionReport(ds, ds.dir.joinpath('transcription.json'))
    stats = tr.report['stats']
    badges = [
        get_badge(rows, 'Glottolog', 'Language_ID'),
        get_badge(rows, 'Concepticon', 'Parameter_ID'),
        get_badge(rows, 'Source')
    ]
    if stats['segments']:
        badges.extend([
            get_badge(
                None,
                'LingPy',
                ratio=(stats['segments'] - stats['lingpy_errors']) / stats['segments']),
            get_badge(
                None,
                'CLPA',
                ratio=(stats['segments'] - stats['clpa_errors']) / stats['segments']),
        ])
    lines.extend(['## Statistics', ' '.join(badges), ''])
    stats_lines = [
        '- **Varieties:** {0:,}'.format(len(totals[0])),
        '- **Concepts:** {0:,}'.format(len(totals[1])),
        '- **Lexemes:** {0:,}'.format(totals[2]),
        '- **Synonymy:** %.2f' % (totals[3][0] / totals[3][1]),
        '- **Cognacy:** %s cognates in %s cognate sets' % tuple(
            map(formatted_number, ds.cognate_stats())),
        '- **Invalid lexemes:** {0:,}'.format(stats['invalid']),
        '- **Tokens:** {0:,}'.format(stats['tokens']),
        '- **Segments:** {0:,} ({1} LingPy errors, {2} CLPA errors, {3} CLPA modified)'
        .format(stats['segments'],
                stats['lingpy_errors'],
                stats['clpa_errors'],
                len(stats['replacements'])),
        '- **Inventory size (avg):** %.2f' % tr.report['stats']['inventory_size'],
    ]
    print('\n'.join(stats_lines))
    lines.extend(stats_lines)

    #trlines, trtotals, trsounds, trerrorsl, trerrorsc = [], [], [], [], []
    #if 'transcription' in cldfds.metadata:
    #    _tr = cldfds.metadata['transcription']
    #    new_badges, new_lines = _transcription_readme(
    #        cldfds.metadata['transcription'])
    #    trsounds += sorted(_tr['segments'])
    #    trerrorsl += [err[0] for err in _tr['errors'].items() if 'lingpy'
    #                  in err[1]]
    #    trerrorsc += [err[0] for err in _tr['errors'].items() if 'clpa' in
    #                  err[1]]
    #    new_badges
    #    trlines.append(
    #        '[%s](%s)' % (cldfds.name, 'cldf/%s.csv' % cldfds.name) \
    #        + ' | {0} | {1} | {2} | {3} | {4:.2f} | '.format(
    #            *new_lines) + \
    #        ' '.join(new_badges)
    #    )
    #    trtotals.append(new_lines)

    #if trlines:
    #    trtotals = [
    #            sum([line[0] for line in trtotals]),
    #            len(set(trsounds)),
    #            len(set(trerrorsl)),
    #            len(set(trerrorsc)),
    #            sum([line[-1] for line in trtotals]) / len(trlines)
    #            ]
    #    trtotals[-1] = trtotals[-1] / len(trlines)
    #    trlines = [
    #            '',
    #            '### Sounds',
    #            '',
    #            'Name  | Sounds (total) | Sounds (unique) | '+\
    #                    'Errors (LingPy) | Errors (CLPA) | '+\
    #                    'Inventory (mean) | Quality ',
    #                    ':---| ---: | ---:| ---:| ---:| ---:| :---:|',
    #                    '**total** | {0} | {1} | {2} | {3} | {4:.2f} | '.format(
    #                        *trtotals)
    #                    ]+\
    #                    trlines

    with ds.dir.joinpath('README.md').open('w', encoding='utf8') as fp:
        fp.write('\n'.join(lines + trlines))
    print(ds.dir.joinpath('README.md'))


def check(args):
    """Checks questionaires for completeness and validity.

    lexibank check [GLOTTOCODE]*

    If no GLOTTOCODEs are specified, all questionaires are checked.
    """
    pass


def main():
    parser = ArgumentParser('pylexibank', readme, download, cldf, list_, report)
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
