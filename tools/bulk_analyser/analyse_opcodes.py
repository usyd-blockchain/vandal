#!/usr/bin/env python3

"""analyse_opcodes.py: produces aggregate opcode stats from EVM bytecode"""

import argparse
import collections
import csv
import glob
import math
import os
import sys
import typing as t

# Add the source directory to the path to ensure the imports work
from os.path import abspath, dirname, join
src_path = join(dirname(abspath(__file__)), "../../src")
sys.path.insert(0, src_path)

# decompiler project imports
import blockparse
import opcodes

DEFAULT_CONTRACT_DIR = 'contracts'
"""Directory to fetch contract files from by default."""

CONTRACT_GLOB = '*_runtime.hex'
"""Files in the contract_dir which match this glob will be processed"""

CSV_FIELDS = ['contract'] + list(sorted(opcodes.OPCODES.keys())) + ['total']
"""fields to appear in output CSV, in this order"""

parser = argparse.ArgumentParser()

parser.add_argument("-c",
                    "--contract_dir",
                    nargs="?",
                    default=DEFAULT_CONTRACT_DIR,
                    const=DEFAULT_CONTRACT_DIR,
                    metavar="DIR",
                    help="the location to grab contracts from (as bytecode "
                         "files).")

parser.add_argument('outfile',
                    type=argparse.FileType('w'),
                    help="CSV file where output statistics will be written, "
                    "one row per contract, with a CSV header as row 1. "
                    "Defaults to stdout if not specified.")

args = parser.parse_args()

def print_progress(progress:int, item:str=""):
  """
  print_progress prints or updates a progress bar with a progress between 0
  and 100.  If given, item is an arbitrary string to be displayed adjacent to
  the progress bar.
  """
  WIDTH = 25
  hashes = min(int(math.floor(progress / (100 // WIDTH))), WIDTH)
  sys.stdout.write('\r[{}] {}% {} '.format('#'*hashes + ' '*(WIDTH - hashes),
                                           progress, item))
  if(progress == 100):
    sys.stdout.write('\n')
  sys.stdout.flush()

def count_opcodes(bytecode:t.Union[str, bytes]) -> collections.Counter:
  """
  count_opcodes counts the number of each type of opcode from a given bytecode
  sequence, returning a dict-compatible collections.Counter.
  """
  parser = blockparse.EVMBytecodeParser(bytecode)
  parser.parse()

  # convert EVMOps to OpCodes
  ops = list(map(lambda op: op.opcode, parser._ops))

  # use Python's Counter to count each
  return collections.Counter(ops), ops


print("Searching for files...")
pattern = join(args.contract_dir, CONTRACT_GLOB)
files = glob.glob(pattern)
print("Located {} contract files matching {}".format(len(files), pattern))

print("Writing output to {}".format(args.outfile.name))

writer = csv.DictWriter(args.outfile, restval=0, fieldnames=CSV_FIELDS)
writer.writeheader()

for i, fname in enumerate(files):
  with open(fname, 'r') as f:
    bname = os.path.basename(f.name)

    # update a progress bar after processing 10 contracts
    if i % 10 == 0 or i+1 == len(files):
      print_progress(math.floor((i+1)/len(files)*100),
                     "{}/{} {}".format(i+1,len(files), bname))

    counts, ops = count_opcodes(f.read().strip())
    row = {op.name: count for op, count in counts.items()}

    # add a "total" column to each row
    row['total'] = sum(row.values())

    # contract filename always goes in first CSV field
    row[CSV_FIELDS[0]] = bname
    writer.writerow(row)
