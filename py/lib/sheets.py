# -*- python -*-

'''

sheets - Generic spreadsheet-like data, a list of rows with named columns.

This module works with basic tabular data, such as found in CSV files.
We assume the first non-comment line consists of column header names, and
that all other columns are of equal width.  Each bit of data is converted
to a number if it appears to be numeric.

The data structure can be accessed like a list, in which case the rows
will be returned as dicts with the column headers as keys.  Either a
plain row or a similar dict can be assigned to a row, and the necessary
conversions happen internally.

This is useful for reading trivial datasets, but it contains no support
for writing the data back; use the lower-level 'csv' or 'ucsv' modules
for read-write applications.

SYNOPSIS

    >>> import sheets

    >>> sheet = Sheet('GOOG.csv')
    >>> print sheet.headers
        ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close']

    >>> sheet.sort(key='Date')
    >>> print sheet[0]              # (day of google ipo)
        { 'Date': '2004-08-19',
          'Open': 100.0,
          'High': 104.06,
          'Low': 95.96,
          'Close': 100.34,
          'Volume': 22351900,
          'Adj Close': 100.34 }

AUTHOR

    Ed Halley (ed@halley.cc) 24 January 2010

'''

#----------------------------------------------------------------------------

import os
import csv

class Sheet (object):
    '''A list of rows, with named columns, such as from a .csv file.'''

    def __init__(self, file=None):
        self.filename = None
        self.columns = []
        self.headers = []
        self.points = []
        self.cursor = -1
        if file:
            self.load(file)

    def load(self, file):
        self.file = file
        if isinstance(file, (str, unicode)):
            if os.path.exists(file):
                self.filename = file
                self.file = file = open(file, 'r')
        if (file):
            self.loadCsv(file)

    def loadCsv(self, file):
        c = csv.reader(file)
        self.headers = h = c.next()
        self.columns = dict( (h[k],k) for k in range(len(h)) )
        for row in c:
            row = map(recipes.num, row)
            self.points.append(row)
        return len(self.points)

    def __len__(self):
        return len(self.points)

    def __getitem__(self, index):
        return dict(zip(self.headers, self.points[index]))

    def __setitem__(self, index, row):
        if isinstance(row, dict):
            row = [ row[h] for h in self.headers ]
        if isinstance(row, (tuple, list)) and len(row) == len(self.headers):
            self.points[index] = list(row)
            return
        raise TypeError('given row value does not match sheet headers')

    def next(self):
        if self.cursor < 0: self.cursor = -1
        self.cursor += 1
        if self.cursor >= len(self.points):
            return None
        return self[self.cursor]

    def prev(self):
        if self.cursor >= len(self.points): self.cursor = len(self.points)
        self.cursor -= 1
        if self.cursor < 0:
            return None
        return self[self.cursor]

    def find(self, key, value, start=0):
        for i in range(start, len(self.points)):
            point = self[i]
            if point[key] == value:
                return point
        return None

    def sort(self, cmp=None, key=None, reverse=False):
        if key in self.headers:
            name = key
            key = lambda x: x[self.columns[name]]
        self.points.sort(cmp=cmp, key=key, reverse=reverse)

    def csv(self, point):
        if isinstance(point, int):
            point = self.points[point]
        if isinstance(point, dict):
            point = [ point[h] for h in self.headers ]
        return ','.join([ str(x) for x in point ])

#----------------------------------------------------------------------------

if __name__ == '__main__':

    s = Sheet()

    print('sheets.py: all internal tests on this module passed.')
