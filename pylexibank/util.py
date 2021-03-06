# coding=utf8
from __future__ import unicode_literals
import logging
import re
import zipfile

from six.moves.urllib.request import urlretrieve
import xlrd
from clldutils.dsv import reader, UnicodeWriter
from clldutils.path import Path, as_posix, copy, TemporaryDirectory
from clldutils.misc import slug
from pycldf.sources import Source, Reference

import pylexibank

logging.basicConfig(level=logging.INFO)
REPOS_PATH = Path(pylexibank.__file__).parent.parent
YEAR_PATTERN = re.compile('\s+\(?(?P<year>[1-9][0-9]{3}(-[0-9]+)?)(\)|\.)')


def clean_form(form):
    form = form.replace('(?)', '').strip()
    if form.startswith('['):
        if form.endswith(']'):
            form = form[1:-1].strip()
        elif ']' not in form[1:]:
            form = form[1:].strip()
    if form.startswith('('):
        if form.endswith(')'):
            form = form[1:-1].strip()
        elif ']' not in form[1:]:
            form = form[1:].strip()
    return form


def split(s, sep=',;', exclude_contexts=None):
    exclude_contexts = dict(exclude_contexts or [('[', ']'), ('(', ')'), ('“', '”')])
    token, context = '', ''
    in_context = []
    ignore_sep = False
    for c in s:
        if c in exclude_contexts:
            ignore_sep = True
            if token and token[-1] == ' ':
                in_context.append(exclude_contexts[c])

        if c in sep and not in_context and not ignore_sep:
            if token.strip():
                yield token.strip(), context.strip() or None
                token, context = '', ''
        else:
            if in_context:
                context += c
            else:
                token += c

        if c in exclude_contexts.values():
            ignore_sep = False
            if in_context and c == in_context[-1]:
                in_context.pop()
                if not in_context:
                    context += ' '

    if token.strip():
        yield token.strip(), context.strip() or None


def xls2csv(fname, outdir=None):
    res = {}
    outdir = outdir or fname.parent
    wb = xlrd.open_workbook(as_posix(fname))
    for sname in wb.sheet_names():
        sheet = wb.sheet_by_name(sname)
        if sheet.nrows:
            path = outdir.joinpath(
                fname.stem + '.' + slug(sname, lowercase=False) + '.csv')
            with UnicodeWriter(path) as writer:
                for i in range(sheet.nrows):
                    writer.writerow([col.value for col in sheet.row(i)])
            res[sname] = path
    return res


def split_by_year(s):
    match = YEAR_PATTERN.search(s)
    if match:
        return s[:match.start()].strip(), match.group('year'), s[match.end():].strip()
    return None, None, s


def get_reference(author, year, title, pages, sources, id_=None, genre='misc'):
    kw = {'title': title}
    id_ = id_ or None
    if author and year:
        id_ = id_ or slug(author + year)
        kw.update(author=author, year=year)
    elif title:
        id_ = id_ or slug(title)

    if not id_:
        return

    source = sources.get(id_)
    if source is None:
        sources[id_] = source = Source(genre, id_, **kw)

    return Reference(source, pages)


def read_csv(path):
    return list(reader(path, dicts=True))


def data_path(*comps, **kw):
    return kw.get('repos', REPOS_PATH).joinpath('datasets', *comps)


def download_and_unpack_zipfiles(url, dataset, *paths):
    """Download zipfiles and immediately unpack the content"""
    with TemporaryDirectory() as tmpdir:
        urlretrieve(url, tmpdir.joinpath('ds.zip').as_posix())
        with zipfile.ZipFile(tmpdir.joinpath('ds.zip').as_posix()) as zipf:
            for path in paths:
                zipf.extract(as_posix(path), path=tmpdir.as_posix())
                copy(tmpdir.joinpath(path), dataset.raw)
