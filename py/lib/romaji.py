#!/usr/bin/python
# romaji - simple romaji-to-kana and kana-to-romaji conversions

'''

The romaji module provides simple conversions between alphabetic (Roman)
strings and Japanese syllable syllable strings in Unicode.

SYNOPSIS

    >> roma(u'\u3053\u3093\u306b\u3061\u306f')
       'konnichiha'

    >> repr( kana('konbanha') )
       u'\u3053\u3093\u3070\u3093\u306f'

    As a convenience, the script works at the command line too.

    $  python  romaji.py  < hiragana.txt > romaji.txt

    $  python  romaji.py  --kana  < romaji.txt > hiragana.txt

AUTHOR

    Ed Halley (ed@halley.cc) 10 December 2007

'''

__all__ = [ 'roma', 'kana', 'gyou', 'tenten', 'maru' ]

#----------------------------------------------------------------------------

import unicodedata ; from unicodedata import *
import re ; from re import *
import codecs
import sys

if sys.version_info >= (3,0):
    def unichr(n): return chr(n)
    def __utf8__(): pass
else:
    def __utf8__(): sys.stdout = codecs.lookup('utf-8')[-1](sys.stdout)

#----------------------------------------------------------------------------

_roma = { }
_kana = { }
_gyou = { } 
_dann = { }
_long = 0

_irregular = { 'SMALL ': 'X',
               'TU': 'TSU', 'TI': 'CHI', 'SI': 'SHI', 'HU': 'FU', 'ZI': 'JI',
               'WU': None, 'YI': None, 'YE': None } # no such 'wu'...
_compounds = { 'JA': 'JI/XA', 'JU': 'JI/XU', 'JO': 'JI/XO',
               'CHA': 'CHI/XYA', 'CHU': 'CHI/XYU', 'CHO': 'CHI/XYO',
               'SYA': 'SHI/XYA', 'SYU': 'SHI/XYU', 'SYO': 'SHI/XYO',
               'SHA': 'SHI/XYA', 'SHU': 'SHI/XYU', 'SHO': 'SHI/XYO',
               } # ji+a, chi+yu, ...
_chiisaiya = 'KGHBPMR' # ki+ya, gi+ya, hi+ya, ...
_punctuals = { ' ': '',
               ',': u'\u3001', # kana-sized grave comma
               '.': u'\u3002', # kana-sized maru period
               '<': u'\u300c', # upper left quote bracket
               '>': u'\u300d', # lower right quote bracket
               '[': u'\u3010', # left lenticular bracket
               ']': u'\u3011', # right lenticular bracket
               '~': u'\u301c', # kana-sized wave tilde
               '-': u'\u30fc', # kana-sized horizontal dash (yokobo)
               '!': u'\uff01', # kana-sized exclamation mark
               '?': u'\uff1f', # kana-sized question mark
               }

def _setup():
    # An internal helper routine that is executed once on module import.
    global _roma
    global _kana
    global _gyou
    global _dann
    global _long
    if _roma: return
    # arrange gyou (syllabary rows) information
    _gyou = { 'A': [ 'A', 'I', 'U', 'E', 'O' ],
              'a': [ 'a', 'i', 'u', 'e', 'o' ],
              'N': [ 'N' ], 'n': [ 'n' ],
              'VU': [ 'VU' ], }
    gyou = 'KA,GA,SA,ZA,TA,DA,NA,HA,BA,PA,MA,YA,RA,WA'.split(',')
    for g in gyou:
        _gyou[g] = [ ]
        _gyou[g.lower()] = [ ]
        for a in _gyou['A']:
            kana = g[:1] + a
            if kana in _irregular: kana = _irregular[kana]
            if not kana: continue
            _gyou[g].append(kana)
            _gyou[g.lower()].append(kana.lower())
    #TODO: set up dann table (u,ku,gu,su,zu,tsu,du,nu,fu,...)
    # find the basic kana and chiisai kana from their unicode data names
    regular = compile(r'(HIRAGANA|KATAKANA) (LETTER) (.+)')
    chiisai = compile(r'(HIRAGANA|KATAKANA) (SMALL LETTER) (.+)')
    for point in range(0x3040, 0x30FF):
        char = unichr(point)
        for pattern in [ regular, chiisai ]:
            match = pattern.match(name(char, ''))
            if match:
                syllable = match.group(3)
                for fix in _irregular:
                    if not _irregular[fix]: continue
                    syllable = syllable.replace(fix, _irregular[fix])
                if match.group(1) == 'HIRAGANA':
                    syllable = syllable.lower()
                if not syllable in _kana:
                    _kana[syllable] = char
                _roma[char] = syllable
    # make simple formulaic compounds with chiisai ya,yu,yo
    for consonant in _chiisaiya:
        for ya in [ 'YA', 'YU', 'YO' ]:
            extended = consonant + 'I/X' + ya
            _compounds[consonant + ya] = extended
            _compounds[(consonant + ya).lower()] = extended.lower()
    # deal with n
    for n in ('N', 'n'):
        _kana[n + "'"] = _kana[n]
    # split and form kana information for each compound
    for syllable in _compounds:
        for lower in (False, True):
            (rk,rx) = _compounds[syllable].split('/')
            if lower:
                (rk,rx) = (rk.lower(), rx.lower())
                syllable = syllable.lower()
            (kk,kx) = (_kana[rk], _kana[rx])
            _kana[syllable] = kk+kx
            _roma[kk+kx] = syllable
    # common kana punctuation
    for mark in _punctuals:
        _kana[mark] = _punctuals[mark]
        _roma[_punctuals[mark]] = mark
    # how long is the longest kana or romaji symbol?
    _long = max([ len(x) for x in _roma ] + [ len(x) for x in _kana ])

def kashira(g):
    '''Returns the top of the gyou row containing the given kana.
    For example, every kana in the "pa" gyou row (pa pi pu pe po) returns "pa".
    '''
    kanaify = False
    if ord(g[0]) > 127:
        g = roma(g)
        kanaify = True
    if g == g.lower():
        if g != 'n':
            g = g[:-1] + 'a'
            fixes = { 'fa':'ha','sha':'sa','tsa':'ta',
                      'ja':'za','cha':'ta','va':'ba' }
            if g in fixes: g = fixes[g]
    elif g == g.upper():
        if g != 'N':
            g = g[:-1] + 'A'
            fixes = { 'FA':'HA','SHA':'SA','TSA':'TA',
                      'JA':'ZA','CHA':'TA','VA':'VU' }
            if g in fixes: g = fixes[g]
    if kanaify:
        g = kana(g)
    return g

def tenten(g):
    '''Returns True if the given kana is written with a dakuten or tenten.'''
    if ord(g[0]) > 127:
        g = roma(g)
    return kashira(g) in [ 'ga','za','da','ba',
                             'GA','ZA','DA','BA' ]

def maru(g):
    '''Returns True if the given kana is written with a handakuten or maru.'''
    if ord(g[0]) > 127:
        g = roma(g)
    return kashira(g) in [ 'pa', 'PA' ]

#----------------------------------------------------------------------------

import random

def choice(g=None, family=None, kanaify=False, rare=False):
    '''Returns a single random kana.

    If a gyou g is given, such as 'KA', the syllable is taken from that
    syllabary row (e.g., 'KA', 'KI', 'KU', 'KE' or 'KO').  Uppercase
    gyou returns katakana, lowercase gyou returns hiragana.  Unicode kana
    of either family will return a random kana in the same gyou, also as
    a Unicode character.

    If a family argument is given, such as 'HIRAGANA' or 'KATAKANA', the
    syllable is taken only from that syllabary.  Family is implied and
    ignored if the gyou is given as a Unicode kana example.

    If you request this routine to kanaify, it is equivalent to calling
    the kana() routine on the selection.

    This does not return any dipthong/compound syllables like 'kyo'.
    '''
    row = gyou(g, family, kanaify, rare)
    roman = random.choice(row)
    if kanaify:
        return kana(roman)
    return roman

def gyou(g, family=None, kanaify=False, rare=False):
    '''Returns a tuple containing all of the syllables'''
    if g is None:
        g = random.choice(list(_gyou.keys()))
    if family and family.lower() in [ 'h', 'hira', 'hiragana', 'hira' ]:
        g = g.lower()
    elif family and family.lower() in [ 'k', 'katakana', 'kata' ]:
        g = g.upper()
    if ord(g[0]) > 127:
        g = roma(g)
        kanaify = True
    g = kashira(g)
    if not g in _gyou:
        raise ValueError('unknown gyou "%s"' % g)
    roman = _gyou[g]
    if not rare:
        roman = [ x for x in roman if not x in
                  set([ 'wi', 'WI', 'we', 'WE' ]) ]
    if kanaify:
        return tuple( [ kana(x) for x in roman ] )
    return tuple(roman)

def dann(d, family=None, kanaify=False, rare=False):
    #TODO:
    return None

#----------------------------------------------------------------------------

def _convert(text, parts):
    # eat the incoming text from start to finish; each time the head
    # of the string matches a known symbol, output that symbol's
    # translated form; look for longer symbols before shorter ones
    global _long
    result = ''
    while text:
        found = False
        for l in reversed(range(1, _long+1)):
            if text[:l] in parts:
                result += parts[text[:l]]
                text = text[l:]
                found = True
                break
        if not found:
            result += text[:1]
            text = text[1:]
    return result

def roma(kana):
    '''Converts a unicode string with hiragana or katakana into romaji.
    Hiragana characters come out in lowercase; katakana in uppercase.
    Any unknown characters (kanji, letters, punctuation) are passed
    through unchanged.
    '''
    kana = re.sub(r'L', r'R', kana)
    kana = re.sub(r'l', r'r', kana)
    roma = _convert(kana, _roma)
    roma = re.sub(r'XTSU([KGTDBPR])', r'\1\1', roma)
    roma = re.sub(r'xtsu([kgtdbpr])', r'\1\1', roma)
    roma = re.sub(r'XTSUCH', r'CCH', roma)
    roma = re.sub(r'xtsuch', r'cch', roma)
    roma = re.sub(r'X(TSU|YA|YU|YO|A|I|U|E|O)', r'\1', roma)
    roma = re.sub(r'x(tsu|ya|yu|yo|a|i|u|e|o)', r'\1', roma)
    roma = re.sub(r"N'", r'N', roma)
    roma = re.sub(r"n'", r'n', roma)
    return roma

def kana(roma):
    '''Converts a string with romaji into hiragana and katakana.
    Lowercase letters are converted to hiragana symbols wherever possible;
    uppercase letters become katakana.  The output is a unicode string.
    Any unknown characters (kanji, letters, punctuation) or unknown letter
    combinations are passed through unchanged.
    '''
    roma = re.sub(r'([KGTDBPRL])\1', r'XTSU\1', roma)
    roma = re.sub(r'([kgtdbprl])\1', r'xtsu\1', roma)
    roma = re.sub(r'([TC]CH)', r'XTSUCH', roma)
    roma = re.sub(r'([tc]ch)', r'xtsuch', roma)
    roma = re.sub(r"[nm]'?([^aiueo]|$)", r"n'\1", roma)
    roma = re.sub(r"[NM]'?([^AIUEO]|$)", r"N'\1", roma)
    return _convert(roma, _kana)

#----------------------------------------------------------------------------

def html(text):
    '''Converts a Unicode string into ASCII HTML by using entities.'''
    result = ''
    for c in text:
        if ord(c) >= 128:
            result += '&#%d;' % ord(c)
        else:
            result += c
    return result

#----------------------------------------------------------------------------

def __test__():

    assert kana("ko n ni chi ha") == u'\u3053\u3093\u306b\u3061\u306f'
    assert roma(u'\u3053\u3093\u3070\u3093\u306f') == "konbanha"

    assert (kana('kyokararyujubyo') ==
            u'\u304d\u3087\u304b\u3089\u308a\u3085\u3058\u3045\u3073\u3087')
    assert kana('kyo kara ryu ju byo') == kana('kyokararyujubyo')
    assert kana('tamagotchi') == u'\u305f\u307e\u3054\u3063\u3061'
    assert kana('tamagotchi') == kana('tamagocchi')

    assert gyou('wa') == ('wa','wo')
    assert gyou('wa',rare=True) == ('wa','wi','we','wo')
    assert gyou('chi') == ('ta','chi','tsu','te','to')
    assert gyou('SHI') == ('SA','SHI','SU','SE','SO')

    assert kashira('a') == 'a'
    assert kashira('tsu') == 'ta'
    assert kashira('SHI') == 'SA'
    assert kashira('FU') == 'HA'
    assert kashira('ji') == 'za'
    assert kashira('SHI') == 'SA'
    assert kashira('pa') == 'pa'
    assert kashira('n') == 'n'
    assert kashira(kana('SHI')) == kana('SA')

    assert tenten('gi')
    assert tenten('bi')
    assert tenten('zi')
    assert tenten('GI')
    assert tenten(kana('di'))
    assert not tenten('ta')
    assert not tenten('PI')
    assert not tenten(kana('chi'))
    assert maru('PU')
    assert maru(kana('pi'))
    assert not maru('bu')
    assert not maru(kana('ji'))

    for x in range(3):
        assert choice('hi') in [ 'ha','hi','fu','he','ho' ]
        assert choice('MU') in [ 'MA','MI','MU','ME','MO' ]
        assert choice(u'\u3072') in [ u'\u306f', u'\u3072', u'\u3075',
                                      u'\u3078', u'\u307b' ]
        y = choice(family='HIRAGANA')
        assert y == y.lower()
        y = choice(family='katakana')
        assert y == y.upper()

    assert kana('tonbo') == kana('tombo')
    assert kana("ton'bo") == kana("tonbo")
    assert roma(kana("tom'bo")) == "tonbo"
    assert roma(kana("shitsumon'")) == "shitsumon"

    assert (html(u'Konnichiwa: \u3053\u3093\u306b\u3061\u306f') ==
            'Konnichiwa: &#12371;&#12435;&#12395;&#12385;&#12399;')

def __pipe__(filter):
    try:
        while True:
            line = sys.stdin.readline()
            if not line: break
            print(filter(line[:-1]))
    except:
        pass

#----------------------------------------------------------------------------

_setup()

if __name__ == '__main__':

    import sys
    sys.argv.pop(0)
    if sys.argv and sys.argv[0] == '--test':
        __test__()
    elif sys.argv and sys.argv[0] == '--kana':
        __utf8__()
        __pipe__(kana)
    else:
        __pipe__(roma)

