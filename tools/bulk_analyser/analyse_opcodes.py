"""opcode_analysis.py: provides functions for analysis opcodes present in a
given CFG"""

## IMPORTS

import collections
import doctest
import os
import sys

# Add the source directory to the path to ensure the imports work
from os.path import abspath, dirname, join
src_path = join(dirname(abspath(__file__)), "../../src")
sys.path.insert(0, src_path)

# Local project imports
import blockparse
import dataflow
import cfg
import evm_cfg
import opcodes
import exporter
import logger
ll = logger.log_low

def analyse_cfg(cfg:cfg.ControlFlowGraph) -> dict:
  agg = collections.Counter()

  for block in cfg.blocks:
    stats = analyse_block(block)
    block._opcode_stats = stats
    agg.update(stats)

  cfg._opcode_stats = agg
  return agg

def analyse_block(block:evm_cfg.EVMBasicBlock) -> dict:
  """
  >>> s = analyse_block(__b('0x0102030405060708090a0b101112131415161718191a'))
  >>> s == {'arithmetic': 22, 'memory': 0, 'storage': 0, 'call': 0}
  True

  >>> s = analyse_block(__b('0x5152535455565758595a5b'))
  >>> s == {'arithmetic': 0, 'memory': 3, 'storage': 2, 'call': 0}
  True

  >>> s = analyse_block(__b('0xf0f1f2f3f4ff'))
  >>> s == {'arithmetic': 0, 'memory': 0, 'storage': 0, 'call': 3}
  True
  """
  stats = {
    'arithmetic': 0,
    'memory': 0,
    'storage': 0,
    'call': 0,
  }

  for op in block.evm_ops:
    if op.opcode.is_arithmetic():
      stats['arithmetic'] += 1

    elif op.opcode.is_memory():
      stats['memory'] += 1

    elif op.opcode.is_storage():
      stats['storage'] += 1

    elif op.opcode.is_call():
      stats['call'] += 1

  return stats

def __b(bytecode:str) -> evm_cfg.EVMBasicBlock:
  # FOR UNIT TEST PURPOSES ONLY
  # Returns a single fake EVMBasicBlock containing all operations from the
  # input bytecode, without regard to block boundaries (RETURN, STOP, etc)
  parser = blockparse.EVMBytecodeParser(bytecode)
  parser.parse()
  return evm_cfg.EVMBasicBlock(evm_ops=parser._ops)

if __name__ == '__main__':
  doctest.testmod()
