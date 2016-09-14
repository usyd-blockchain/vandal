"""evm_cfg.py: Classes for processing disasm output and building a CFG"""

import typing

import cfg
import utils
import opcodes

class EVMBasicBlock(cfg.BasicBlock):
  """
  Represents a single basic block in the control flow graph (CFG), including
  its parent and child nodes in the graph structure.
  """

  # Separator to be used for string representation
  __BLOCK_SEP = "\n---"

  def __init__(self, entry:int=None, exit:int=None):
    """
    Creates a new basic block containing operations between the
    specified entry and exit instruction counters (inclusive).
    """
    super().__init__(entry, exit)

    self.evm_ops = []
    """List of EVMOps contained within this EVMBasicBlock"""

  def __str__(self):
    """Returns a string representation of this block and all ops in it."""
    return "\n".join(str(op) for op in self.evm_ops) + self.__BLOCK_SEP

  def split(self, entry:int) -> 'EVMBasicBlock':
    """
    Splits current block into a new block, starting at the specified
    entry op index. Returns a new EVMBasicBlock with no preds or succs.

    Args:
      entry: unique index of EVMOp from which the block should be split. The
             EVMOp at this index will become the first EVMOp of the new
             BasicBlock.
    """
    # Create the new block and assign the code line ranges
    new = type(self)(entry, self.exit)
    self.exit = entry - 1

    # Split the code ops between the two blocks
    new.evm_ops = self.evm_ops[entry - self.entry:]
    self.evm_ops = self.evm_ops[:entry - self.entry]

    # Update the block pointer in each line object
    self.__update_evmop_refs()
    new.__update_evmop_refs()

    return new

  def __update_evmop_refs(self):
    # Update references back to parent block for each opcode
    # This needs to be done when a block is split
    for op in self.evm_ops:
      op.block = self


class EVMOp:
  """
  Represents a single EVM operation.
  """
  def __init__(self, pc:int, opcode:opcodes.OpCode, value:int=None):
    """
    Create a new EVMOp object from the given params which should correspond to
    disasm output.

    Args:
      pc: program counter of this operation
      opcode: VM operation code
      value: constant int value or None in case of non-PUSH operations

    Each line of disasm output is structured as follows:

    PC <spaces> OPCODE <spaces> => CONSTANT

    where:
      - PC is the program counter
      - OPCODE is an object representing an EVM instruction code
      - CONSTANT is a hexadecimal value with 0x notational prefix
      - <spaces> is a variable number of spaces

    For instructions with no hard-coded constant data (i.e. non-PUSH
    instructions), the disasm output only includes PC and OPCODE; i.e.

    PC <spaces> OPCODE

    If None is passed to the value parameter, the instruction is assumed to
    contain no CONSTANT (as in the second example above).
    """

    self.pc = pc
    """Program counter of this operation"""

    self.opcode = opcode
    """VM operation code"""

    self.value = value
    """Constant int value or None"""

    self.block = None
    """EVMBasicBlock object to which this line belongs"""

  def __str__(self):
    if self.value is None:
      return "{0} {1}".format(hex(self.pc), self.opcode)
    else:
      return "{0} {1} {2}".format(hex(self.pc), self.opcode, hex(self.value))

  def __repr__(self):
    return "<{0} object {1}: {2}>".format(
      self.__class__.__name__,
      hex(id(self)),
      self.__str__()
    )
