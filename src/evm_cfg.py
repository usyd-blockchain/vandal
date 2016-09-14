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
  def __init__(self, entry:int=None, exit:int=None):
    """Creates a new basic block containing disassembly lines between the
    specified entry index and the specified exit index (inclusive)."""
    super().__init__(entry, exit)

    self.evm_ops = []
    """List of EVMOps contained within this EVMBasicBlock"""

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
