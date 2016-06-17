# -*- python -*-

'''

An alternative to the standard Python getopt module.

SYNOPSIS

    >>> import getopts ; from getopts import *
    >>> import sys

    >>> options = { 'flag': False,   # -f, --flag, --flag=Yes, -f False
                    'number': 3,     # -n 2, -n=4, --number=6, +nnn, +number
                    'mode': 'fast',  # -m slow, --mode slow, --mode=slow
                    'Names': [],     # -N Mary, --names John,Bill
                  }

    >>> others = getopts(sys.argv, options)

    >>> options['flag']
    True

    >>> options['number']
    4

    >>> options['Names']
    [ 'Mary', 'John', 'Bill' ]

AUTHOR

    Ed Halley (ed@halley.cc) 14 November 2008

SEE ALSO

    The standard Python 'getopt' module, with GNU- and K&R-style options.

'''

from __future__ import print_function

import re
import sys

#----------------------------------------------------------------------------

'''An alternative to the standard Python getopt module.'''

def boolify(value):
    '''Take a friendly user input value, and turn it into True or False.'''
    try: value = value.lower()
    except: pass
    if value in (True, 1, 'y', 'yes', 'on', 'enable'):
        return True
    if value in (None, False, 0, 'n', 'no', 'off', 'disable'):
        return False
    return True

def getopt(arg, tail, opt, default):
    '''Super-lightweight implementation of one --option=value parsing.
    Supports:
        -o       / --option        (returns True if default is a bool)
        -o=value / --option=value  (returns value in same type as default)
        -o value / --option value  (returns value in same type as default)
        +ooo     / +option         (returns int(default) plus each repeat)
    Lists append comma-separated values.  Integers can be incremented.
    Pops values from tail (usually remainder of argv list) only if required.
    '''
    value = None
    o = opt[0]
    opt = opt.lower()
    match = re.match(r"^(-%s|--%s)$" % (o, opt), arg)
    if match:
        if isinstance(default, (bool, type(None))):
            return True
        if not len(tail):
            raise ValueError('Option --%s needs an argument.' % opt)
        value = tail.pop(0)
    else:
        match = re.match(r"^(-%s|--%s)=(.*)$" % (o, opt), arg)
        if match:
            value = match.group(2)
        else:
            match = re.match(r"^\+((%s+)|(%s))$" % (o, opt), arg)
            if match:
                try:
                    d = int(default)
                    if match.group(2): value = d+len(match.group(2))
                    if match.group(3): value = d+1
                except:
                    raise ValueError('Option --%s cannot be +counted.' % opt)
    if value is None:
        return default
    if isinstance(default, (list, tuple)):
        return list(default) + value.split(',')
    if isinstance(default, bool):
        return boolify(value)
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value

def usage(this, options):
    '''Super-lightweight implementation of command-line usage help.
    Does not have anything particularly wordy about the meanings of each
    option and inputfiles.
    '''
    err = sys.stderr
    print('Usage: ', this, '<options>', '<inputfiles>', file=err)
    print('Options and their (default) values:', file=err)
    for option in options:
        print('\t--%-15s\t(%s)' % (option, repr(options[option])), file=err)
    sys.exit(1)

def getopts(argv, options, this=None, help=True):
    '''Super-lightweight implementation of command-line argument parsing.
    Pass an argument list (usually the unmodified sys.argv), and a dict
    of default values, like:
        options = { 'flag': False,   # -f, --flag, --flag=Yes, -f False
                    'number': 3,     # -n 2, -n=4, --number=6, +nnn, +number
                    'mode': 'fast',  # -m slow, --mode slow, --mode=slow
                    'Names': [],     # -N Mary, --names John,Bill
                    }
    Assumes initial letters are unique and --options are lowercase.
    (Especially note the -n/--number and -N/--names examples above.)
    Does no fancy unique-prefix magic to determine useful abbreviations.
    Subsequent values overwrite earlier values, or are appended for lists.

    By default, --help, -h, -? are reserved and aborts with a printed
    usage statement on standard error output. This can be disabled with
    a help=False argument.
    
    Non-options can be interspersed with options.  Anything after a lone
    '--' are non-option arguments.  Returns list of all non-option
    arguments in the order they were found.  Aborts with a printed usage
    statement on standard error output, and an error return code, if
    given an invalid option value.

    '''
    if not this:
        this = argv.pop(0)
    original = options.copy()
    remains = [ ]
    while argv:
        arg = argv.pop(0)
        if arg == '--':
            remains.extend(argv)
            break
        if help and arg in ('-h', '-?', '--help'):
            usage(this, original)
            break
        if len(arg) > 1 and arg[0] in ('-','+'):
            for opt in options:
                try:
                    options[opt] = getopt(arg, argv, opt, options[opt])
                except ValueError as ex:
                    print(ex.message, file=sys.stderr)
                    usage(this, original)
        else:
            remains.append(arg)
    return remains

#----------------------------------------------------------------------------

if __name__ == '__main__':

    options = { 'flag': False,   # -f, --flag, --flag=Yes, -f False
                'number': 3,     # -n 2, -n=4, --number=6, +nnn, +number
                'mode': 'fast',  # -m slow, --mode slow, --mode=slow
                'Names': [],     # -N Mary, --names John,Bill
                }

    try: others = getopts(['getopts.py'], options)
    except: assert False
    assert others == []
    assert options['flag'] == False
    assert options['number'] == 3
    assert options['mode'] == 'fast'
    
    try: others = getopts(['getopts.py',
                           'before','+nnn','middle','--mode','slow','after'],
                          options)
    except: assert False
    assert others == ['before','middle','after']
    assert options['flag'] == False
    assert options['number'] == 6
    assert options['mode'] == 'slow'

    try: others = getopts(['before','-n=9','--mode','odd','--','-f'],
                          options, this='getopts.py')
    except: assert False
    assert others == ['before','-f']
    assert options['flag'] == False
    assert options['number'] == 9
    assert options['mode'] == 'odd'

    try: others = getopts(['-n',12,'-f'],
                          options, this='getopts.py')
    except: assert False
    assert others == []
    assert options['flag'] == True
    assert options['number'] == 12
    assert options['mode'] == 'odd'

    print('getopts.py: all internal tests on this module passed.')
