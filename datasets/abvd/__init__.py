# coding=utf-8
from __future__ import unicode_literals, print_function
from collections import defaultdict

from clldutils.misc import slug

from pylexibank.providers import abvd
from pylexibank.dataset import Unmapped
from tqdm import tqdm

from .author_notes_map import MAP

SECTION = 'austronesian'
TRANSCRIPTION_REPORT_CFG = dict(column='Segments', segmentized=True)


def download(dataset, **kw):
    abvd.download(dataset, SECTION)


def cldf(dataset, concepticon, **kw):
    concept_map = {
        c.attributes['url'].split('v=')[1]: c.concepticon_id
        for c in dataset.conceptlist.concepts.values()}

    l_map = {int(l['ID']): l['GLOTTOCODE'] for l in dataset.languages if l['GLOTTOCODE']}
    gl_map = dataset.glottocode_by_iso
    wordlists = []
    for xml in tqdm(list(dataset.raw.glob('*.xml')), desc='xml-to-wordlist', leave=False):
        wl = abvd.Wordlist(dataset, xml, SECTION)
        if int(wl.language.id) in l_map:
            wl.language.glottocode = l_map[int(wl.language.id)]
        elif wl.language.iso:
            if wl.language.iso in gl_map:
                wl.language.glottocode = gl_map[wl.language.iso]
        wordlists.append(wl)

    source_map = defaultdict(lambda: (None, None))
    for wlid, (author, notes) in MAP.items():
        source_map[wlid.split('-', 1)[1]] = (slug(author), notes.strip())

    unmapped = Unmapped(lambda r: int(r[0]))
    for wl in tqdm(wordlists, desc='wordlist-to-cldf', leave=False):
        ds = wl.to_cldf(concept_map, unmapped, *source_map[wl.id])
        cognates = list(wl.cognates())
        #dataset.cognates.extend(iter_alignments(ds, cognates, column='Value', method='progressive'))
        dataset.cognates.extend(cognates)
    unmapped.pprint()
