"""cfg.py: Base classes for representing Control Flow Graphs (CFGs)"""

class ControlFlowGraph:
  """Generic Control Flow Graph (CFG)"""
  def __init__(self):
    """Create a new empty ControlFlowGraph"""

    self.blocks = []
    """List of CFGNode objects"""

    self.root = None
    """The root CFGNode object, or None for the empty graph"""

  def __len__(self):
    return len(self.blocks)

  def __str__(self):
    return "\n".join(str(b) for b in self.blocks)

  def edge_list(self):
    """Returns a list of the CFG's edges in the form (pred, succ)."""
    return [(p,s) for s in p.successors for p in self.blocks]

class CFGNode:
  """
  Represents a single basic block (node) in a control flow graph (CFG),
  including references to its predecessor and successor nodes in the graph
  structure.
  """

  # Separator to be used for string representation of blocks
  __BLOCK_SEP = "\n---"

  def __init__(self, entry:int=None, exit:int=None):
    """
    Creates a new CFG node containing code lines between the
    specified entry index and the specified exit index (inclusive).
    """

    self.entry = entry
    """Index of the first code line contained in this node"""

    self.exit = exit
    """Index of the last code line contained in this node"""

    self.lines = []
    """List of CodeLines contained in this node"""

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

  def split(self, entry:int) -> 'CFGNode':
    """
    Splits this CFGNode into a new CFGNode, from at the specified
    entry line number. Returns the new CFGNode.
    """
    # Create the new block and assign the code line ranges
    new = type(self)(entry, self.exit)
    self.exit = entry - 1

    # Split the code lines between the two nodes
    new.lines = self.lines[entry-self.entry:]
    self.lines = self.lines[:entry-self.entry]

    return new
