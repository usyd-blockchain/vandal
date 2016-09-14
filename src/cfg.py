"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

import abc
import patterns

class ControlFlowGraph(abc.ABC):
  """Abstract base class for a Control Flow Graph (CFG)"""
  @abc.abstractmethod
  def __init__(self):
    """Create a new empty ControlFlowGraph"""

    self.blocks = []
    """List of BasicBlock objects"""

    self.root = None
    """The root BasicBlock object, or None for the empty graph"""

  def __len__(self):
    return len(self.blocks)

  def __str__(self):
    return "\n".join(str(b) for b in self.blocks)

  def edge_list(self):
    """Returns a list of the CFG's edges in the form (pred, succ)."""
    return [(p,s) for p in self.blocks for s in p.succs]

  def accept(self, visitor:patterns.Visitor):
    """
    Visitor design pattern: accepts a Visitor instance and visits every node
    in the CFG in an arbitrary order.

    Args:
      visitor: instance of a Visitor
    """
    for b in self.blocks:
      b.accept(visitor)


class BasicBlock(abc.ABC):
  """
  Abstract base class for a single basic block (node) in a CFG. Each block has
  references to its predecessor and successor nodes in the graph structure.
  """

  # Separator to be used for string representation
  __BLOCK_SEP = "\n---"

  @abc.abstractmethod
  def __init__(self, entry:int=None, exit:int=None):
    """
    Creates a new CFG node containing code lines between the
    specified entry index and the specified exit index (inclusive).
    """

    self.entry = entry
    """Index of the first code line contained in this node"""

    self.exit = exit
    """Index of the last code line contained in this node"""

    self.preds = []
    """List of nodes which pass control to this node (predecessors)"""

    self.succs = []
    """List of nodes which receive control from this node (successors)"""

    self.has_unresolved_jump = False
    """True if the node contains a jump whose destination is computer"""

  def __len__(self):
    """Returns the number of lines of code contained within this block."""
    return self.exit - self.entry

  def __str__(self):
    """Returns a string representation of this block and all lines in it."""
    return "\n".join(str(l) for l in self.lines) + self.__BLOCK_SEP

  def __hash__(self):
    return id(self)

  def accept(self, visitor:patterns.Visitor):
    """
    Visitor design pattern: accepts a Visitor instance and visits this node.

    Args:
      visitor: instance of a Visitor
    """
    visitor.visit(self)
