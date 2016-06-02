#!/usr/bin/python
#
# Brainfuck Interpreter
# Copyright 2011 Sebastian Kaspari
# https://github.com/pocmo/Python-Brainfuck/blob/master/brainfuck.py
#
# Usage: ./brainfuck.py [FILE]

#----------------------------------------------------------------------------

import getch

def execute(filename):
  f = open(filename, "r")
  evaluate(f.read())
  f.close()

def evaluate(code):
  code = cleanup(list(code))
  bracemap = buildbracemap(code)

  cells = [ 0 ]
  codeptr = 0
  cellptr = 0

  while codeptr < len(code):
    command = code[codeptr]

    if command == ">":
      cellptr += 1
      if cellptr == len(cells): cells.append(0)

    if command == "<":
      cellptr = 0 if cellptr <= 0 else cellptr - 1

    if command == "+":
      cells[cellptr] = cells[cellptr] + 1 if cells[cellptr] < 255 else 0

    if command == "-":
      cells[cellptr] = cells[cellptr] - 1 if cells[cellptr] > 0 else 255

    if command == "[" and cells[cellptr] == 0:
      codeptr = bracemap[codeptr]
    if command == "]" and cells[cellptr] != 0:
      codeptr = bracemap[codeptr]
    if command == ".":
      sys.stdout.write(chr(cells[cellptr]))
    if command == ",":
      cells[cellptr] = ord(getch.getch())
      
    codeptr += 1

def cleanup(code):
  return list(filter(lambda x: x in '.,[]<>+-', code))

def buildbracemap(code):
  temp_bracestack, bracemap = [], {}

  for position, command in enumerate(code):
    if command == "[": temp_bracestack.append(position)
    if command == "]":
      start = temp_bracestack.pop()
      bracemap[start] = position
      bracemap[position] = start
  return bracemap

#----------------------------------------------------------------------------

if __name__ == '__main__':

  import os
  import sys
  self = sys.argv.pop(0)

  if sys.argv:
    execute(sys.argv[0])
  else:
    print("Usage: %s <filename>" % self)
