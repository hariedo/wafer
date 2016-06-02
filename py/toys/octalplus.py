#!/opt/local/bin/python
# Octal Plus - A six-bit microcontroller simulator and its assembler

__all__ = [ 'Machine', 'Assembler', 'Debugger', 'OSCII' ]

#----------------------------------------------------------------------------

'''

NAME

    Octal Plus - A six-bit microcontroller simulator and its assembler.

SYNOPSIS

    %  python octalplus.py
    Command: help

    %  python octalplus.py  --demo

ABSTRACT

    The Machine class implements the microcontroller, which can be loaded
    with machine code and stepped through its virtual instruction
    execution.

    The Assembler class implements a dual-pass assembler, turning a
    human- readable assembly language into an encoded byte stream ready
    to load into the PROM area of the microcontroller.

    The Debugger class implements a rich visual single-stepping debugger
    able to summarize the whole microcontroller state and walk through
    the given assembler source code interactively.

    A six-bit system is not particularly useful for many real-world
    tasks, but it may be suitable for learning how such devices work.
    The simplicity is such that one can fully learn and come to
    appreciate every single detail about the implementation and
    capabilities in a very short time period.  (An even simpler four-bit
    system can be devised as an introduction but is usually not even
    necessary for those already familiar with simple digital logic.)

DESCRIPTION

    The address space of the machine is six bits wide, and the byte size
    is six bits.  Given this arrangement, it is natural to express
    addresses and byte values in two-digit octal notation, from o00 ~
    o77.  (The assembler also understands a leading zero 000 ~ 077 or
    decimals d0 ~ d63.)

    More than half of the address space is dedicated to PROM program
    space.  The rest is split between scratch RAM variable space, a
    general-purpose stack for calling subroutines or saving/restoring
    registers, and a special input/output area with several memory-mapped
    interfaces where virtual "hardware" devices can be connected and
    controlled.

    Yes, any microcontroller experts out there are going to point to this
    as an absurd example of bad microcontroller design.  It borrows from
    the non-pipelined days of accumulator-based microprocessor design,
    with an odd medley of addressing modes, an unusual extra register
    configuration, almost no thought whatsoever to decodable opcode
    bytes, and definitely no consideration to the distinction between
    clocks and cycles.  Everything is memory-mapped rather than expecting
    specialized buses for data, address, i/o or other structures.

    Rather than focus on the low-level hardware implementation, this
    design is intended for high-level software developers or children who
    have no deep experience in either.  It exhibits a variety of machine
    concepts in a very compressed python implementation, so the informal
    user may learn some basics of using assembly language or how hardware
    is related to software.  Again, it is not intended to have an optimal
    arrangement ready for silicon implementation or real-world work.

OSCII

    Since we are working with six-bit bytes, this is not enough for the
    full range of ASCII characters.  For display purposes, we invent a
    new character set called "OSCII", which includes uppercase alphabetic
    characters, digits and punctuation represented in characters d0~d63.
    The simulated hardware would ostensibly support virtual peripherals
    that understood OSCII and produced or displayed characters properly.
    The assembler also can use OSCII literals to represent characters in
    the object code.

AUTHOR

    Ed Halley (ed@halley.cc) 15 April 2008

'''

#----------------------------------------------------------------------------

OSCII = (' ABCDEFG' +
         'HIJKLMNO' +
         'PQRSTUVW' +
         'XYZ01234' +
         '56789.!@' +
         '#$%^&*-=' +
         '+:;?<>[]' +
         '{}()\'\"/\\')

ENCODING = dict( zip( list(OSCII), range(0100) ) )

OPCODES = [ 'clr',  'clr',  'jmp',  'ql0', 'clr',  'clr',  'clr',  'qs0',
            'load', 'load', 'load', 'ql1', 'jc',   'jm',   'jz',   'qs1',
            'save', 'save', 'save', 'ql2', 'jnc',  'jnm',  'jnz',  'qs2',
            'pop',  'pop',  'ret',  'ql3', 'rol',  'inc',  'pop',  'qs3',
            'push', 'push', 'call', 'ql4', 'ror',  'dec',  'push', 'qs4',
            'load', 'load', 'stop', 'ql5', 'load', 'load', 'load', 'qs5',
            'add',  'add',  'add',  'ql6', 'and',  'and',  'and',  'qs6',
            'sub',  'sub',  'sub',  'ql7', 'or',   'or',   'or',   'qs7' ]

import random
import time
import re
import os

def unknown(): return random.randint(0, 077)
def widest(strings):
    n = 0
    for string in strings:
        n = max(n, len(string))
    return n

#----------------------------------------------------------------------------

class Machine:

    '''

    The Machine simulates a six-bit "Octal Plus" microcontroller.

    Instructions are one or two six-bit bytes, and the address space is
    six bits wide, for a total of 64 bytes including PROM and RAM and I/O.

    Machine registers include:

        A - accumulator
        B - base
        I - instruction
        S - stack
        F - flags  (including Carry, Minus, Zero)

    Address space is arranged accordingly:

        o00~o17 = RAM
                  o00~o07 = quick page
                  o10~o17 = stack space
        o20~o27 = I/O
                  o20~023 = "oscii" display screen RAM
                  o24 = read/write direction
                  o25 = six general directable i/o pins
                  o26 = slow clock ticker (once per o1000 clock steps)
                  o27 = fast clock ticker (once per o0010 clock steps)
        o30 ~ o77 = PROM

          01234567
         +--------
        0|QQQQQQQQ   Q = quick page RAM
        1|SSSSSSSS   S = stack space RAM
        2|DDDDIOTT   D, I, O, T = mapped I/O
        3|PPPPPPPP   P = program space PROM
        4|PPPPPPPP
        5|PPPPPPPP
        6|PPPPPPPP
        7|PPPPPPPP

    On powerup, RAM, I/O and PROMs are not explicitly cleared.
    The stack pointer is set above the stack space, ready for a push.
    The instruction pointer is set to the bottom of the PROM area).
    All flags are cleared.

    Input/Output:

        There are six virtual programmable I/O pins.

        One memory-mapped byte (at o25) is the I/O ports register.

        One memory-mapped byte (at o24) defines the read/write direction
        for each corresponding port bit in the I/O register.  A high bit
        (a non-zero) allows programs to write to the corresponding bit in
        the I/O register.  Written bits can be read back by the program,
        combined with any input state supplied by the hardware.

        By default, all input pins are unpredictable and noisy, and all
        output pins are ignored.  Override the Machine.inp() method to
        "connect" and provide true input data, and override the
        Machine.out() method to "connect" and react to programs writing
        to the output ports.

    Ticker:

        Two memory-mapped bytes are automatically updated according to an
        internal clock, to allow for crude timing.  The clock is divided
        down to a useful speed internally.  The byte at o27 is
        incremented every eight instruction steps.  The byte at o26 is
        automatically incremented when the first byte overflows, or every
        o1000 or d512 instruction steps.  Once the high-order ticker
        overflows, which is every o100000 or d32768 steps, they both wrap
        to zero.

    Display:

        Four memory-mapped bytes are assumed to be reserved for display
        output purposes.  These bytes operate as plain RAM with no
        special behavior, in case your program needs more RAM space.  The
        debugging Machine.dump() helper method calls attention to these
        bytes in a separate OSCII display area, and the Machine.display()
        method is called with their contents every instruction step, to
        allow an override to react to their updated contents.

    '''

    RAM = 000 ; RAMLEN = 024
    PROM = 030 ; PROMLEN = 050
    SCREEN = 020
    DIRECTIONS = 024 # high bit indicates an output port
    PORTS = 025
    TICKSLOW = 026
    TICKFAST = 027
    STACK = 020 # just above stack's top, actually

    REGISTERS = dict( zip( list('ABISF'), range(5) ) )
    RESET = { 'A': 000, 'B': 000, 'I': PROM, 'S': STACK, 'F': 000 }
    FLAGS = { 'C': 004, 'M': 002, 'Z': 001 }

    STOP = 052
    POPS = set([ 030, 031, 032, 036 ])
    PUSHES = set([ 040, 041, 042, 046 ])
    BASES = set([ 012, 022, 062, 072, 056, 066, 076 ])
    IMMEDIATES = set([ 002, 010, 011, 014, 015, 016,
                       020, 021, 024, 025, 026,
                       042, 054, 055, 056,
                       060, 064, 070, 074 ])

    SOURCES = [ 'X',   'X',   '_',   0, 'X', 'X', 'X',   'A',
                '[_]', '[_]', '[B]', 1, '_', '_', '_',   'A',
                'A',   'B',   'A',   2, '_', '_', '_',   'A',
                '[S]', '[S]', '[S]', 3, 'A', 'B', '[S]', 'A',
                'A',   'B',   '_',   4, 'A', 'B', 'F',   'A',
                'B',   'A',   'X',   5, '_', '_', '_',   'A',
                '_',   'B',   '[B]', 6, '_', 'B', '[B]', 'A',
                '_',   'B',   '[B]', 7, '_', 'B', '[B]', 'A' ]

    TARGETS = [ 'A',   'B',   'I',   'A', 'C', 'M', 'Z',   0,
                'A',   'B',   'A',   'A', 'I', 'I', 'I',   1,
                '[_]', '[_]', '[B]', 'A', 'I', 'I', 'I',   2,
                'A',   'B',   'I',   'A', 'A', 'B', 'F',   3,
                '[S]', '[S]', 'I',   'A', 'A', 'B', '[S]', 4,
                'A',   'B',   'I',   'A', 'A', 'B', 'F',   5,
                'A',   'A',   'A',   'A', 'A', 'A', 'A',   6,
                'A',   'A',   'A',   'A', 'A', 'A', 'A',   7 ]

    def __init__(self):
        '''Connect memory and onboard registers. All are uninitialized.'''
        self.memory = [ unknown() for x in range(0100) ]
        self.registers = [ unknown() for x in Machine.REGISTERS ]
        self.clock = unknown() * unknown()
        self.speed = 0.1

    def reset(self):
        '''Reset all registers to stable and known values, ready for run.'''
        for register in Machine.RESET:
            self.set(register, Machine.RESET[register])
        self.clock = 0
        self.tick()
        self.io()

    def set(self, address, value, prom=False):
        '''Latch a value into a memory location, a named register or flag.

            machine.set('A', 055) # register A loaded with octal 55
            machine.set('C', 1)   # flag register C loaded with 1
            machine.set(Machine.PORTS, 055) # memory location asserted

        To intentionally latch new contents into PROM, specify the
        prom=True override.  The execution of machine code itself cannot
        modify PROM.  Any I/O port pins programmed for INPUT cannot be
        written; the input bits are masked off automatically here.
        '''
        value &= 077
        if address in Machine.FLAGS:
            f = Machine.REGISTERS['F']
            if value != 0: value = Machine.FLAGS[address]
            self.registers[f] &= ~Machine.FLAGS[address]
            self.registers[f] |= value
        elif address in Machine.REGISTERS:
            self.registers[Machine.REGISTERS[address]] = value
        else:
            address &= 077
            if address == Machine.PORTS:
                value &= self.memory[Machine.DIRECTIONS]
                self.memory[address] |= self.memory[address]
            if address < Machine.PROM or prom:
                self.memory[address] = value

    def get(self, address):
        '''Query a value from a memory location, a named register or flag.'''
        if address == 'X': return 0
        if address in Machine.FLAGS:
            f = Machine.REGISTERS['F']
            value = self.registers[f] & Machine.FLAGS[address]
            if value != 0: value = 1
            return value
        if address in Machine.REGISTERS:
            return self.registers[Machine.REGISTERS[address]]
        address &= 077
        return self.memory[address]

    def tick(self):
        '''Update the internal hardware clock and the two ticking ports.'''
        clock = self.clock
        clock >>= 3
        self.set(Machine.TICKFAST, clock & 077)
        clock >>= 6
        self.set(Machine.TICKSLOW, clock & 077)
        self.clock += 1

    def out(self, value):
        '''Overridable; control external "devices" from six output bits.'''
        pass

    def inp(self):
        '''Overridable; read up to six input bits.'''
        value = unknown()
        return value

    def display(self, values):
        '''Overridable; react to the memory-mapped "screen" contents.'''
        pass

    def io(self):
        '''Perform the programmable input/output port logic.'''
        outputs = self.memory[Machine.DIRECTIONS]
        inputs = (~outputs) & 077
        value = self.memory[Machine.PORTS] & outputs
        self.out(value)
        value |= self.inp() & inputs
        self.memory[Machine.PORTS] = value
        self.display(self.memory[Machine.SCREEN:Machine.SCREEN+4])

    def fetch(self):
        '''Retrieve byte at address I, then increment I.'''
        i = self.get('I')
        byte = self.get(i)
        self.set('I', i+1)
        return byte

    def locate(self, address, operand):
        '''Determine the effective address, following any indirection.'''
        if address == '[_]': return self.get(operand)
        if address == '[S]': return self.get('S')
        if address == '[B]': return self.get('B')
        return address

    def flag(self, value):
        '''Set the flags according to a register result.'''
        self.set('Z', not (value & 077))
        self.set('M', (value < 0) or (value & 0040))
        self.set('C', (value < 0) or (value & 0300))

    def operate(self, opcode, value):
        '''Perform interior logic for arithmetic or branching operation.'''
        a = self.get('A')
        c = self.get('C')
        opclass = OPCODES[opcode]
        if opclass in [ 'jc', 'jnc', 'jm', 'jnm', 'jz', 'jnz' ]:
            flag = self.get( opclass[-1:].upper() )
            if not 'n' in opclass: flag = not flag
            if flag: value = self.get('I')
        if opclass == 'call':
            self.set(self.get('S'), self.get('I'))
        if opclass == 'add': value = a + value + c
        if opclass == 'sub': value = a - value - c
        if opclass == 'and': value = a & value
        if opclass == 'or': value = a | value
        if opclass == 'inc': value += 1
        if opclass == 'dec': value -= 1
        if opclass == 'ror':
            # new c will be taken from (1<<6) bit
            value = (value >> 1) | ((value & 001) << 6) | (c << 5)
        if opclass == 'rol':
            # new c will be taken from (1<<6) bit
            value = (value << 1) | ((value & 040) << 6) | (c)
        if opclass in [ 'load', 'clr', 'add', 'sub', 'and', 'or',
                       'ror', 'rol', 'inc', 'dec', 'pop', 'mov' ]:
            self.flag(value)
        value &= 077
        return value

    def execute(self, opcode, operand=None):
        '''Update whole machine state for one instruction.'''
        # predecrement stack for pushes
        if opcode in Machine.PUSHES:
            self.set('S', self.get('S')-1)
        # retrieve our value
        source = Machine.SOURCES[opcode]
        if source == '_':
            value = operand
        elif source == '[_]':
            value = self.locate(source, operand)
        else:
            value = self.get(self.locate(source, operand))
        # perform operation on value alone
        value = self.operate(opcode, value)
        # commit our value
        target = Machine.TARGETS[opcode]
        if target == '_':
            raise Error, 'cannot write to _ immediate'
        elif target == '[_]':
            target = operand
        self.set(self.locate(target, operand), value)
        # postincrement base for base access
        if opcode in Machine.BASES:
            self.set('B', self.get('B')+1)
        # postincrement stack for pops
        if opcode in Machine.POPS:
            self.set('S', self.get('S')+1)

    def stopped(self):
        '''Checks if a STOP instruction has been encountered.'''
        return self.get(self.get('I')) == Machine.STOP

    def sleep(self):
        '''Pause inserted between steps to set the run rate.'''
        if self.speed is not None:
            time.sleep(self.speed)

    def step(self):
        '''Fetch the full instruction, and execute it.'''
        if self.stopped():
            return False
        opcode = self.fetch()
        operand = None
        if opcode in Machine.IMMEDIATES:
            operand = self.fetch()
        self.execute(opcode, operand)
        self.tick()
        self.io()
        self.sleep()
        return True

    def run(self, limit=None):
        '''Executes instructions until a STOP instruction is encountered.'''
        while self.step():
            if limit is None:
                continue
            limit -= 1
            if limit <= 0:
                return False
        return True

    def prom(self, rom):
        '''Burn a byte image into the PROM area of the machine.'''
        rom = rom[:Machine.PROMLEN]
        for i in range(len(rom)):
            self.set(i + Machine.PROM, ENCODING[rom[i]], prom=True)

    def load(self, ram):
        '''Commit a byte image into the RAM area of the machine.'''
        ram = ram[:Machine.RAMLEN]
        for i in range(len(ram)):
            self.set(i, ENCODING[ram[i]])

    def save(self, begin=000, end=077):
        '''Retrieve a byte image from any part of the machine.'''
        img = ''
        for i in range(begin, end+1):
            img += OSCII[self.get(i)]
        return img

#----------------------------------------------------------------------------

class Assembler:

    '''

    The Octal Plus assembler takes in a filename, or a list of source
    code lines, and parses the input to encode a byte-for-byte image of
    the PROM area of the Octal Plus machine.

    Instructions:

        CLEAR <flag>
        CLEAR <register>
        LOAD <target>, <source>  (synonym MOVE)
        SAVE <source>, <target>  (synonym STORE)
        PUSH <register>
        POP <register>
        JMP <address>
        JZ <address>  / JM <address>  / JC <address>
        JNZ <address> / JNM <address> / JNC <address>
        CALL <address>
        RETURN
        ADD A, <value>
        SUB A, <value>
        AND A, <value>
        OR A, <value>
        ROL A / ROR A
        INC B / DEC B
        STOP                     (synonym HALT)

    Arguments for Instructions:

        Flags for CLEAR are any of C, M or Z.
        Registers for CLEAR, PUSH and POP are any of A, B, or F.
        Targets for LOAD are the A or B registers, or F flag register.
        Sources for SAVE are limited to A or B registers.
        Addresses for JMP, JZ, JNZ, JM, JNM, JC, JNC, CALL are absolute.

        Sources for LOAD may be an immediate value, an immediate
        [indirect] address, or a base [B] indirect address.  More on
        these addressing terms below.

        Targets for STORE may be an immediate [indirect] address, or a
        base [B] indirect address.  More on these addressing terms below.

    Addressing Modes:

        Immediate Value: Many arguments are literal absolute values to be
        used in the core operation of the instruction.  These may be
        specified as an octal constant, a decimal constant, an OSCII
        character in quotes, or an absolute symbolic label with an
        ampersand.

        LOAD A, o35 ; loads A register with value o35 (decimal d29)
        LOAD B, "$" ; loads B register with OSCII $, value o51 (d41)
        ADD A, d28 ; adds d28 (o34) into A register
        CALL &print ; pushes I register, then jumps to print routine

        Immediate Indirect: Some instructions can take a value which
        represents an address, and the memory contents at that address
        are read or written instead.

        LOAD A, [o23] ; assigns memory contents at o23 to A register
        SAVE B, [&screen] ; assigns B register value to screen memory
        ADD A, [d28] ; adds memory contents at d28 (o34) to A register

        Base Indirect: Some instructions use the B register to decide
        an indirect address.  There is no immediate argument other than
        [B].  The value of B is taken to be the address for reading or
        writing, and the value at that address is read or written.
        After the instruction executes, the B register is incremented
        automatically, making it easier to work on a series of data in
        memory.

        LOAD A, [B] ; loads A from memory address specified by B
        SAVE A, [B] ; saves A to memory address specified by B
        OR A, [B] ; bitwise OR to memory address specified by B into A
          ; and after each of these instructions, increment B

        Finally, there is a special "quick" addressing mode for loading
        and saving the A register indirectly to the first 8 addresses
        o00~o07.  This is intended to reduce the size of programs
        slightly, by not requiring a separate operand to specify the
        intended memory address.  The indirect address is a part of the
        machine instruction opcode itself.

        QS3 ; just like SAVE A, [o03] but more efficiently encoded
        QL6 ; just like LOAD A, [o06] but more efficiently encoded

        The assembler does not currently optimize with equivalent
        quick-load and quick-save instructions if your program source
        chooses to use the longer save and load statements.  Their use is
        entirely up to the programmer.

    Other Assembler Statements:

        Symbolic labels can be defined with a line beginning with a
        colon (:) character.  If defined anywhere in the program, then
        instructions can refer to that label with an ampersand (&)
        character.

        LOAD A, [B]
        JZ &skip ; jumps to SAVE instruction below, if Z flag is set
        HALT
        :skip
        SAVE A, [o34]

        Symbolic labels with specific addresses can be defined to any
        address value.  This is useful for naming variables in RAM or
        naming specific memory-mapped hardware ports.  These can be
        used for symbolic constants too.

        :screen=o20
        :cursor=o07
        :asterisk="*"

        Literal data bytes can be stored in the PROM for use by the
        program.  Currently, only a single quoted OSCII string can be
        specified.  To include a single-quote in a string, use
        double-quotes, and vice versa.

        = 'OCTOPUS' ; stores bytes o17, o03, o24, o17, o20, o25, o23

    '''

    IDENTIFIER = r'[a-zA-Z_][a-zA-Z0-9_]*'
    OCTAL = r'[0o]([0-7]+)'
    DECIMAL = r'[d]([0-9]+)'
    QUOTED = r'(?:\'.*?\'|\".*?\")'
    ADDRESS = r'\&%s' % IDENTIFIER
    LITERAL = r'(?:%s|%s)' % (OCTAL, QUOTED)

    OPERANDS = [ 'A', 'B', '_', '', 'C', 'M', 'Z', '',
                 'A', 'B', 'A', '', '_', '_', '_', '',
                 'A', 'B', 'A', '', '_', '_', '_', '',
                 'A', 'B', '',  '', 'A', 'B', 'F', '',
                 'A', 'B', '_', '', 'A', 'B', 'F', '',
                 'A', 'B', '',  '', 'A', 'B', 'F', '',
                 'A', 'A', 'A', '', 'A', 'A', 'A', '',
                 'A', 'A', 'A', '', 'A', 'A', 'A', '' ]

    DIRECTANDS = [ '',    '',    '',    '', '',  '',  '',    '',
                   '[_]', '[_]', '[B]', '', '',  '',  '',    '',
                   '[_]', '[_]', '[B]', '', '',  '',  '',    '',
                   '',    '',    '',    '', '',  '',  '',    '',
                   '',    '',    '',    '', '',  '',  '',    '',
                   'B',   'A',   '',    '', '_', '_', '_',   '',
                   '_',   'B',   '[B]', '', '_', 'B', '[B]', '',
                   '_',   'B',   '[B]', '', '_', 'B', '[B]', '' ]

    SYNONYMS = { 'clear': 'clr',
                 'store': 'save', 'sto': 'save',
                 'pull': 'pop',
                 'move': 'load', 'mov': 'load',
                 'return': 'ret',
                 'halt': 'stop' }

    def __init__(self):
        self.labels = { }
        self.errors = [ ]
        self.listing = [ ]
        self.source = '(unknown)'
        self.code = [ Machine.STOP ] * Machine.PROMLEN
        self.encoded = ''

    def log(self, line, address=None):
        '''Log a program listing line, giving address and opcode bytes.'''
        if address is not None:
            self.listing.append(('@%02o| ' % address) + line)
        else:
            self.listing.append('   | ' + line)

    def error(self, line, tier, message):
        '''Log an error; does not stop the assembly process.'''
        message = '%s(%d): %s: %s' % (self.source, line, tier, message)
        self.errors.append(message)

    def immediate(self, word, labels=False):
        '''Tries to match a single argument into an immediate value.
        Supports &label symbols, and 3, o23, 023, d19, "X" literals.
        If labels=True, tries to follow and return defined label values.
        Returns None if unsuccessful at parsing the intent of the user.
        '''
        if re.match(Assembler.ADDRESS + '$', word):
            word = word[1:]
            if labels and word in self.labels:
                return self.labels[word]
            return word
        m = re.match(Assembler.OCTAL + '$', word)
        if m:
            return int(m.group(1), 8)
        m = re.match(r'[0-7]$', word)
        if m:
            return int(word, 8)
        m = re.match(Assembler.DECIMAL + '$', word)
        if m:
            return int(m.group(1))
        m = re.match(Assembler.QUOTED + '$', word)
        if m:
            word = word[1:-1]
            if len(word) == 1:
                if word[0] in ENCODING:
                    return ENCODING[word[0]]
                return None
        return None

    def instruction(self, line):
        '''Returns a list of bytes for the encoding of one instruction.
        Returns None for a unparseable line, but it is up to the caller
        to log the error.  The list will include numeric bytes for known
        encoding, or strings like '&label' for symbolic references.
        '''
        line = line.strip()
        line = line.replace('" "', '"_"').replace("' '", "'_'")
        line = line.replace('","', '"`"').replace("','", "'`'")
        words = line.split(' ')
        words = sum( map(lambda word: word.split(','), words), [] )
        words = [ word.replace('`', ',') for word in words if word ]
        # first word is the opclass
        opclass = words[0].lower()
        if opclass in Assembler.SYNONYMS:
            opclass = Assembler.SYNONYMS[opclass]
        words = [ word.strip() for word in words ]
        # our opcode space is so small,
        # we just try all possible instructions against the opclass!
        for opcode in range(0100):
            if opclass != OPCODES[opcode]:
                continue
            # no operands (RETURN, QS3, etc.)
            if len(words) == 1:
                if Assembler.OPERANDS[opcode] != '':
                    continue
                return [ opcode ]
            # one operand (CALL _, JNZ _, POP B, etc.)
            # may end up as one encoded byte or two
            if len(words) == 2:
                if Assembler.OPERANDS[opcode] == '':
                    continue
                left = words[1]
                if Assembler.OPERANDS[opcode] == '_':
                    left = left.replace('_', ' ')
                    value = self.immediate(left)
                    if value is None:
                        continue
                    return [ opcode, value ]
                if left.upper() == Assembler.OPERANDS[opcode]:
                    return [ opcode ]
            # two operands (LOAD A, _; OR A, [B]; SAVE A, [_]; etc.)
            # may end up as one encoded byte or two
            if len(words) == 3:
                if Assembler.OPERANDS[opcode] == '':
                    continue
                if Assembler.DIRECTANDS[opcode] == '':
                    continue
                left = words[1]
                right = words[2].replace('+', '')
                if left.upper() != Assembler.OPERANDS[opcode]:
                    continue
                if Assembler.DIRECTANDS[opcode] == '_':
                    right = right.replace('_', ' ')
                    value = self.immediate(right)
                    if value is None:
                        continue
                    return [ opcode, value ]
                if Assembler.DIRECTANDS[opcode] == '[_]' and right[0] == '[':
                    right = right[1:-1].replace('_', ' ')
                    value = self.immediate(right)
                    if value is None:
                        continue
                    return [ opcode, value ]
                if right.upper() == Assembler.DIRECTANDS[opcode]:
                    return [ opcode ]
        return None

    def read(self, source):
        '''Reads or processes the assembly source code.'''
        lines = [ ]
        if isinstance(source, (list,tuple)):
            lines = source
            self.source = 'input'
        elif os.path.exists(source):
            file = open(source, 'r')
            lines = file.readlines()
            file.close()
            self.source = source
        else:
            lines = source.split('\n')
            self.source = 'input'
        return lines

    def dump(self, encoding):
        '''Shows encoded bytes in friendly octal/symbol format.'''
        text = [ ]
        for byte in encoding:
            if isinstance(byte, str):
                text.append('&'+byte)
            else:
                text.append('o%02o' % byte)
        return ', '.join(text)

    def apply(self, address, encoding, lineno):
        '''Injects the encoded bytes from a statement into the PROM image.
        Encoded bytes might be integers or string '&address' symbols.
        Any attempt to apply to non-PROM addresses is caught.
        '''
        code = self.code
        for byte in encoding:
            PROMTOP = Machine.PROM + Machine.PROMLEN
            if address < Machine.PROM or address >= PROMTOP:
                self.error(lineno, 'Error',
                           'Code address is outside PROM space.')
            else:
                code[address - Machine.PROM] = byte
                address = (address + 1) % 0100
        return address

    def assemble(self, source):
        '''Processes a complete set of assembly source code.
        Returns the encoded byte stream for PROM if successful.
        Also builds the error list and opcode listing outputs.
        '''
        count = 0
        code = self.code
        lines = self.read(source)
        home = False
        address = Machine.PROM
        #self.log( '; octalplus listing of %s' % self.source)
        # read source code
        for line in lines:
            count += 1
            line = line.strip()
            if line == '': continue
            if line[0] == ';':
                self.log(line)
                continue
            if not home:
                if line[0] != ':':
                    label = 'home'
                    self.labels[label] = address
                    self.log( ":%-19s ;" % label, address )
                    home = True
            # absolute label
            m = re.match(r':(%s)=(%s)' % (Assembler.IDENTIFIER,
                                          Assembler.LITERAL), line)
            if m:
                label = m.group(1)
                if label in self.labels:
                    self.error(count, 'Warning',
                               'Redefining label :%s' % label)
                address = self.immediate(m.group(2))
                self.labels[label] = address
                self.log( ":%-15s=o%02o ;" % (label, address), address )
                continue
            # normal label
            m = re.match(r':(%s)' % Assembler.IDENTIFIER, line)
            if m:
                home = True
                label = m.group(1)
                if label in self.labels:
                    self.error(count, 'Warning',
                               'Redefining label :%s' % label)
                self.labels[label] = address
                self.log( ":%-19s ;" % label, address )
                continue
            # instruction
            encoding = self.instruction(line)
            if encoding is not None:
                text = self.dump(encoding)
                self.log( "   %-17s ; %s" % (line[:20], text), address )
                address = self.apply(address, encoding, count)
                continue
            # literal data
            if line[0] == '=':
                line = line[1:].strip()
                original = line
                encoding = [ ]
                while line:
                    if line[0] in " \t":
                        line = line[1:]
                        continue
                    if line[0] in "\'\"":
                        quote = line[0]
                        line = line[1:]
                        while line and line[0] != quote:
                            char = line[0]
                            line = line[1:]
                            encoding.append(ENCODING[char])
                    else:
                        self.error(count, 'Error',
                                   'Could not parse literal data: ' + line)
                        break
                if encoding:
                    text = self.dump(encoding)
                    self.log( "   %-17s ; %s" % (original[:17], text), address )
                    address = self.apply(address, encoding, count)
                continue
            # unknown
            self.error(count, 'Error',
                       'Could not parse line: ' + line)
        # fix up relocations
        encoded = ''
        for byte in code:
            if isinstance(byte, str):
                label = byte
                if not label in self.labels:
                    self.error(count, 'Error',
                               'Never resolved address: &%s' % label)
                    byte = 0
                else:
                    byte = self.labels[label]
            encoded += OSCII[byte]
        #for label in self.labels:
        #    self.log( '%-20s ; &%s=o%02o' %
        #                    ('', label, self.labels[label]) )
        if not self.errors:
            self.encoded = encoded
        return encoded

#----------------------------------------------------------------------------

class Debugger:

    '''

    A rudimentary interactive debugger for the Octal Plus machine.

    Upon startup, a fresh Machine and Assembler are loaded with no code.
    Commands can be issued on an internal command-line interface to
    perform various adjustments of the machine state, or to load and
    assemble an external file with Octal Plus assembly code.

    Help is available at the command prompt, so it is not included here.

    '''

    def __init__(self):
        self.machine = Machine()
        self.machine.reset()
        self.assembler = Assembler()
        self.messages = [ ]
        self.quit = False
        self.width = 80

    def message(self, message):
        '''Appends another message to appear above the command prompt.'''
        self.messages.append(message)

    def update(self):
        '''Updates all debugger status displays.'''
        view = self.dump()
        if os.name in [ 'nt' ]:
            os.system('cls')
        else:
            os.system('clear')
        print 'Octal Plus 6-bit Microcontroller Emulator by Ed Halley'
        print 'Hit <Enter> to step, type "H" for help, or "Q" to quit.'
        if view:
            print
            for line in view:
                print line
        if self.messages:
            print
            for line in self.messages:
                print line
        print

    def step(self):
        '''Run one instruction step on the attached machine.'''
        self.machine.step()
        if self.machine.stopped():
            self.message('Machine reached a STOP instruction.')

    def go(self, limit=None):
        '''Runs until a STOP instruction has been encountered.'''
        while self.machine.step():
            self.update()
            if limit is None:
                continue
            limit -= 1
            if limit <= 0:
                break
        if self.machine.stopped():
            self.message('Machine reached a STOP instruction.')

    def run(self):
        '''Updates the display an executes commands until user quits.'''
        self.quit = False
        while not self.quit:
            self.update()
            self.messages = [ ]
            try:
                command = raw_input('Command: ')
                self.execute(command)
            except EOFError:
                print
                self.quit = True

    def assemble(self, code):
        '''Replaces the on-board assembler with a new one to assemble code.'''
        self.assembler = Assembler()
        bytes = self.assembler.assemble(code)
        if self.assembler.errors:
            self.assembler.listing = [ ]
            self.messages = self.assembler.errors[:]
        else:
            self.machine.prom(bytes)

    def help(self):
        '''
        STEP - execute current instruction at I and advance
        NEAT - load "." throughout RAM and "%" (STOP) throughout PROM
        RESET - reset all machine registers to powerup values
        GO - run until a STOP encountered, or d1000 steps
        <register> <value> - load register with value
           e.g.,  A "$" - loads A with o51 (OSCII $)
        <address> <value> - poke memory with value
           e.g.,  o20 o00 - stores value o00 into memory location o20
           (be careful, this command can burn bytes to PROM)
        READ <file> - load, assemble and burn new program into PROM
        '''
        self.messages = Debugger.help.__doc__.split("\n")[1:-1]

    def execute(self, command):
        '''Perform whatever debugger operation commanded.'''
        words = command.split(' ')
        verb = words[0].lower()
        if verb in [ 'q', 'quit', 'exit' ]:
            self.quit = True
            return
        if verb in [ '', 'step' ]:
            return self.step()
        if verb in [ 'h', 'help' ]:
            return self.help()
        if verb in [ 'r', 'reset' ]:
            return self.machine.reset()
        if verb in [ 'g', 'go', 'run' ]:
            return self.go(limit=1000)
        if verb in [ 'n', 'neat' ]:
            self.assembler = Assembler()
            self.machine.load('.' * Machine.RAMLEN)
            self.machine.prom(OSCII[Machine.STOP] * Machine.PROMLEN)
            return self.machine.reset()
        if verb in [ 'l', 'read' ]:
            filename = command[len(verb)+1:]
            self.assemble(filename)
            return
        # register assign
        if verb in [ 'i', 'a', 'b', 's', 'f', 'c', 'm', 'z' ]:
            verb = verb.upper()
            if len(words) < 2:
                self.message('Expected a value to load in %s.' % verb)
                return
            value = self.assembler.immediate(words[1], labels=True)
            if value is None:
                self.message('Bad value to load in %s.' % verb.upper())
                return
            self.machine.set(verb, value)
            self.message('Register %s loaded with o%02o.' % (verb, value))
            return
        # memory assign
        addr = self.assembler.immediate(words[0], labels=True)
        if addr is not None:
            value = self.assembler.immediate(words[1], labels=True)
            if value is None:
                self.message('Bad value (second argument) to load in memory.')
                return
            self.machine.set(addr, value, prom=True)
            self.message('Memory at o%02o set to o%02o.' % (addr, value))
            return
        self.message('Command "%s" not recognized. "h" for help.' % command)

    def pack(self, view, lines):
        '''Append a new column flush to the right of existing view lines.'''
        width = widest(view)
        while len(view) < len(lines):
            view.append(' '*width)
        while len(lines) < len(view):
            lines.append('')
        width = widest(lines)
        lines = [ (line+' '*width)[:width] for line in lines ]
        for i in range(len(view)):
            view[i] += ' ' + lines[i]
        return view

    def dbyte(self, byte):
        if not isinstance(byte, int):
            return '~%s~' % repr(byte)
        if byte < 0 or byte >= 0100:
            return '~%o~' % byte
        return OSCII[byte]

    def drow(self, row):
        return self.machine.save(row*8, row*8+7)

    def dump(self):
        '''Format all view columns for the user to see.'''
        view = [ '' ] * 10
        if self.machine:
            view = self.pack(view, self.dmem())
            view = self.pack(view, self.dreg())
        if self.assembler and self.assembler.listing:
            view = self.pack(view, self.dobj())
        for i in range(len(view)):
            view[i] = view[i][:self.width-1]
        return view

    def dmem(self):
        '''Format a view column for memory space represented in OSCII.'''
        v = [ '   01234567',
              '  +--------',
              ' 0|%000008s' % self.drow(0),
              ' 1|%000008s' % self.drow(1),
              ' 2|%000008s' % self.drow(2),
              ' 3|%000008s' % self.drow(3),
              ' 4|%000008s' % self.drow(4),
              ' 5|%000008s' % self.drow(5),
              ' 6|%000008s' % self.drow(6),
              ' 7|%000008s' % self.drow(7) ]
        return v

    def dreg(self):
        '''Format a view for comprehensive machine registers study.'''
        mach = self.machine
        a = mach.get('A')
        b = mach.get('B') ; db = self.dbyte(b)
        B = mach.get(b) ; dB = self.dbyte(B)
        i = mach.get('I') ; di = self.dbyte(i)
        op = mach.get(mach.get('I'))
        op = '%s=%s' % (self.dbyte(op), OPCODES[op])
        s = mach.get('S') ; ds = self.dbyte(s)
        dirs = mach.get(Machine.DIRECTIONS)
        dirs = ''.join([ 'v^'[not (dirs&x)]
                         for x in (040,020,010,4,2,1) ])
        io = mach.get(Machine.PORTS)
        io = ''.join([ '10'[not (io&x)]
                       for x in (040,020,010,4,2,1) ])
        disp = mach.save(Machine.SCREEN, Machine.SCREEN+3)
        v = [ ' A=o%02o \'%s\'' % (a, self.dbyte(a)),
              ' B=o%02o \'%s\' [%s]' % (b, db, dB),
              ' I=o%02o \'%s\' [%s]' % (i, di, op),
              ' S=o%02o \'%s\'' % (s, ds),
              ' C= %d' % mach.get('C'),
              ' M= %d' % mach.get('M'),
              ' Z= %d' % mach.get('Z'),
              ' dir: %s' % dirs,
              ' i/o: %s' % io,
              ' dis: [%s]' % disp ]
        if self.assembler and self.assembler.listing:
            v[2] = '%-20s -->' % v[2]
        return v

    def find(self, listing, addr):
        '''Find a line in an assembled object listing for a given address.'''
        addr = '@%02o|' % addr
        ix = len(listing)-1
        while ix >= 0:
            if listing[ix][:len(addr)] == addr:
                return ix
            ix -= 1
        return None

    def dobj(self):
        '''Format a view column for the assembled object listing.'''
        listing = self.assembler.listing
        # try for I first, work backward
        ix = None
        addr = self.machine.get('I')
        stop = addr
        while ix is None:
            ix = self.find(listing, addr)
            if ix is None:
                addr = (addr - 1) & 077
                if addr == stop:
                    break
        if ix is None:
            return [ '' ] * 10
        # show window on listing with I line as [2]
        v = [''] * 10
        for i in range(ix-2, ix+8):
            if i >= 0 and i < len(listing):
                v[i-(ix-2)] = listing[i]
        return v

#----------------------------------------------------------------------------
# some rudimentary unit tests to ensure proper operation with small programs

def __run(code, dump=False):
    '''Assemble and run code from scratch, returning the halted machine.'''
    from testing import __ok__
    assy = Assembler()
    code = assy.assemble(code)
    __ok__(not assy.errors)
    machine = Machine()
    machine.reset()
    machine.speed = None
    if assy.errors:
        for error in assy.errors:
            print error
    else:
        if dump:
            for line in assy.listing:
                print line
            print repr(code)
        machine.prom(code)
        halted = machine.run(limit=5000)
        __ok__(halted)
    return machine

def __expect(machine, states):
    '''Quick test to compare addresses with expected stored values.'''
    from testing import __ok__
    for state in states:
        if isinstance(states[state], str) and len(states[state]) > 1:
            data = machine.save(state, state+len(states[state])-1)
        else:
            data = machine.get(state)
        __ok__(data, states[state], '%s' % state)

def __testRegisters():
    '''Checks that the basic machine registers operate as expected.'''
    import testing ; from testing import __ok__
    machine = __run( '''
                     load A, o10
                     load B, o22
                     push A
                     push B
                     pop F
                     stop
                     ''' )
    __expect(machine, { 'A':010, 'B':022,
                        'I':(Machine.PROM+7),
                        'S':(Machine.STACK-1) } )
    __expect(machine, { 'C':0, 'M':1, 'Z':0 } )
    if testing.__fails__():
        machine.dump()

def __testMemory():
    '''Ensures that the memory in the machine works as expected.'''
    import testing ; from testing import __ok__
    machine = Machine()
    machine.load('.' * Machine.RAMLEN)
    machine.prom('%' * Machine.PROMLEN)
    # ram writes should succeed
    for i in range(Machine.RAM, Machine.RAM+Machine.RAMLEN):
        machine.set(i, i)
        if machine.get(i) != i:
            __ok__(False)
            break
    # prom writes should fail silently
    for i in range(Machine.PROM, Machine.PROM+Machine.PROMLEN):
        machine.set(i, i)
        if machine.get(i) != ENCODING['%']:
            __ok__(False)
            break

def __testAddressing():
    '''Assembles and runs instructions using different addressing modes.'''
    import testing ; from testing import __ok__
    machine = __run( '''
                     load A, "0"
                     qs0
                     add A, o01
                     save A, [o01]
                     load B, o02
                     add A, o01
                     save A, [B]
                     clear B
                     load A, [B]
                     sub A, "0"
                     qs3
                     load A, [B]
                     sub A, "0"
                     qs4
                     load A, [B]
                     sub A, "0"
                     qs5
                     ql1
                     stop
                     ''' )
    __expect(machine, { 'A':ENCODING['1'] } )
    __expect(machine, { 000:ENCODING['0'], 003:000,
                        001:ENCODING['1'], 004:001,
                        002:ENCODING['2'], 005:002 } )
    if testing.__fails__():
        machine.dump()

def __testStack():
    '''Fill the stack with known values, and check it did the right thing.'''
    import testing ; from testing import __ok__
    __ok__(Machine.STACK >= 9)
    machine = __run( '''
                     load A, "*"
                     save A, [o%02o]
                     load B, o10
                     load A, "A"
                     :loop
                     push A
                     add A, o01
                     dec B
                     jnz &loop
                     stop
                     ''' % (Machine.STACK-9) )
    __expect(machine, { 'S':(Machine.STACK-8),
                        (Machine.STACK-8):'HGFEDCBA',
                        (Machine.STACK-9):ENCODING['*'] } )
    if testing.__fails__():
        machine.dump()

def __test__():
    '''Run all self-tests.
        % python -c "import octalplus ; octalplus.__test__()" 
    '''
    import testing ; from testing import __ok__
    if not testing.__fails__(): __testMemory()
    if not testing.__fails__(): __testRegisters()
    if not testing.__fails__(): __testAddressing()
    if not testing.__fails__(): __testStack()
    testing.__report__()

#----------------------------------------------------------------------------
# run an interesting but trivial example program

def __demo__():

    debug = Debugger()

    code = '''; animate "octo" letters on display
           ;
           :main
             ; copy from data to screen
             load B, &data
             load A, &screen
             call &putc
             call &putc
             call &putc
             call &putc
             ; fill screen with blanks
             load B, &screen
             load A, " "
             save A, [B]
             save A, [B]
             save A, [B]
             save A, [B]
             ; endless loop
             jmp &main
           :putc
             ; copy from [B] to [A]
             ; post-incrementing both
             push B
             push A
             load A, [B]
             pop B
             save A, [B]
             move A, B
             pop B
             inc B
             return
           :data
             = "OCTO"
           :screen=o20
           '''

    debug.execute('NEAT')
    debug.assemble(code)
    debug.message('An example program, "OCTO", has been assembled for you.')
    debug.message('To the left, a chart displays every memory location.')
    debug.message('Registers and machine status in the middle at a glance.')
    debug.message('A detailed listing shows program code on the right.')
    #debug.machine.load('.' * Machine.RAMLEN)
    #    debug.machine.reset()
    #    debug.machine.prom(code)
    debug.run()

#----------------------------------------------------------------------------

if __name__ == '__main__':

    import sys
    self = sys.argv.pop(0)
    if not sys.argv:
        print('usage:  %s  <test|demo>' % self)

    for arg in sys.argv:
        if arg in [ 'test', '--test', '-t' ]:
            __test__()
        if arg in [ 'demo', '--demo', '-d' ]:
            __demo__()

