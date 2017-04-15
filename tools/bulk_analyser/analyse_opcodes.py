"""analyse_opcodes.py: produces aggregate opcode stats from EVM bytecode"""

import argparse
import collections
import csv
import glob
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

CSV_FIELDS = (
  'contract',  # contract filename
  'arith',     # number of arithmetic opcodes
  'memory',    # number of memory opcodes
  'storage',   # number of storage opcodes
  'calls',     # number of contract call opcodes
  'other'      # number of other opcodes
)
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
                    nargs='?',
                    type=argparse.FileType('w'),
                    default=sys.stdout,
                    help="CSV file where output statistics will be written, "
                    "one row per contract, with a CSV header as row 1. "
                    "Defaults to stdout if not specified.")

args = parser.parse_args()

def count_opcodes(bytecode:t.Union[str, bytes]) -> dict:
  parser = blockparse.EVMBytecodeParser(bytecode)
  parser.parse()

  # convert EVMOps to OpCodes
  ops = list(map(lambda op: op.opcode, parser._ops))

  # use Python's Counter to count each
  return collections.Counter(ops), ops

writer = csv.DictWriter(args.outfile, fieldnames=CSV_FIELDS)
writer.writeheader()

for fname in glob.glob(join(args.contract_dir, CONTRACT_GLOB)):
  with open(fname, 'r') as f:

    counts, ops = count_opcodes(f.read().strip())

    arith   = sum([c for op, c in counts.items() if op.is_arithmetic()])
    memory  = sum([c for op, c in counts.items() if op.is_memory()])
    storage = sum([c for op, c in counts.items() if op.is_storage()])
    calls   = sum([c for op, c in counts.items() if op.is_call()])
    other   = sum(counts.values()) - (arith + memory + storage + calls)

    row = {
      'arith': arith,
      'memory': memory,
      'storage': storage,
      'calls': calls,
      'other': other,
    }

    assert sum(row.values()) == len(ops)

    row['contract'] = os.path.basename(f.name)
    writer.writerow(row)
