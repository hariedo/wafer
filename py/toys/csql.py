#!/usr/bin/python

#
# Perform SQL Queries on CSV data files.
# Inspired by another 'csql' by Jeff Epler <jepler@unpythonic.net>
#
# This version allows you to work with one or more CSV file tables, just
# by referring to the tables inside your query with filenames ending in
# .csv extension.
#
# Example:   select SKU,QTY,PRICE from inventory.csv
#
# Surely there are a million SQL things that this little script can't do.
#

import os
import sqlite3

try:
    import ucsv as csv
except:
    import csv

#----------------------------------------------------------------------------
# manage whole database

class Database:

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.text_factory = str
        self.tables = { }

    def get_table_name(self, filename):
        name = os.path.basename(filename)
        if name.lower().endswith('.csv'):
            name = name[:-4]
        #TODO: safe name removes any non-alphanum
        name = name.replace('.', '_')
        return name

    def create_table(self, name, headers):
        self.tables[name] = headers
        headers = ','.join(headers)
        cursor = self.connection.cursor()
        cursor.execute('create table %s (%s);' % (name, headers))
        return cursor

    def import_table(self, name, file):
        data = csv.reader(file)
        name = self.get_table_name(name)
        if name in self.tables:
            return
        headers = [ ]
        cursor = None
        places = ''
        clips = 0
        count = 0
        for row in data:
            if not len(row):
                continue
            if str(row[0]).startswith('#'):
                continue
            if not headers:
                headers = [ each.strip() for each in row ]
                places = ','.join('?' * len(headers))
                cursor = self.create_table(name, headers)
                continue
            if len(row) < len(headers):
                row.extend([''] * (len(headers)-len(row)))
            elif len(row) > len(headers):
                clips += 1
            cursor.execute('insert into %s values (%s);' % (name, places),
                           row[:len(headers)])
            count += 1
        return count

    def execute_query(self, query):
        cursor = self.connection.cursor()
        cursor.execute(query)
        return cursor

#----------------------------------------------------------------------------
# perform query and form output

if __name__ == '__main__':

    import re
    import sys

    sys.argv.pop(0)

    if not sys.argv:
        print('usage:     csql   <query>')
        print('example:   csql   "select first,last,phone from phones.csv"')
        exit(1)

    query = sys.argv.pop(0)

    db = Database()
    eof = 'Ctrl+D'
    if os.name == 'nt':
        eof = 'Ctrl+Z'

    words = re.findall(r'(?i)[a-z0-9.]+\.csv|stdin', query)
    for word in words:
        if word.lower().endswith('.csv'):
            db.import_table(word, open(word))
            query = query.replace(word, db.get_table_name(word))
            continue
        if word.lower() == 'stdin':
            if not 'stdin' in db.tables:
                if sys.stdin.isatty():
                    msg = ('Importing data from STDIN; '+
                           '%s twice to conclude.') % eof
                    print >>sys.stderr, msg
                db.import_table('stdin', sys.stdin)

    results = csv.writer(sys.stdout, dialect='excel')
    cursor = db.execute_query(query)
    results.writerow( [ field[0] for field in cursor.description ] )
    for row in cursor:
        results.writerow(row)
