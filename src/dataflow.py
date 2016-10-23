"""dataflow.py: fixed-point, dataflow, static analyses for CFGs"""

import cfg
import evm_cfg
import tac_cfg
import lattice
import memtypes


def stack_analysis(cfg:tac_cfg.TACGraph,
                   die_on_empty_pop:bool=False, reinit_stacks:bool=True,
                   hook_up_stack_vars:bool=True, hook_up_jumps:bool=True):
  """
  Determine all possible stack states at block exits. The stack size should be
  the maximum possible size, and the variables on the stack should obtain the
  maximal set of values possible at that stack position at a given point of
  program execution.

  Args:
    cfg: the graph to analyse.
    die_on_empty_pop: raise an exception if an empty stack is popped.
    reinit_stacks: reinitialise all blocks' exit stacks to be empty.
    hook_up_stack_vars: after completing the analysis, propagate entry stack
                        values into blocks.
    hook_up_jumps: Connect any new edges that can be inferred after performing
                   the analysis

  If we have already reached complete information about our stack CFG structure
  and stack states, we can use die_on_empty_pop and reinit_stacks to discover
  places where empty stack exceptions will be thrown.
  """

  # Initialise all entry and exit stacks to be empty.
  if reinit_stacks:
    for block in cfg.blocks:
      block.symbolic_overflow = False
      block.entry_stack = memtypes.VariableStack()
      block.exit_stack = memtypes.VariableStack()

  # Initialise a worklist with blocks that have no precedessors
  queue = [block for block in cfg.blocks if len(block.preds) == 0]
  visited = {block: False for block in cfg.blocks}

  # Churn until we reach a fixed point.
  while queue:
    curr_block = queue.pop(0)

    # Build the entry stack by joining all predecessor exit stacks.
    pred_stacks = [pred.exit_stack for pred in curr_block.preds]
    entry_stack = memtypes.VariableStack.join_all(pred_stacks)

    # If variables were obtained from deeper than there are extant
    # stack items, the program is possibly popping from an empty stack.
    if die_on_empty_pop and (entry_stack < curr_block.delta_stack.empty_pops):
      raise RuntimeError("Popped empty stack in {}.".format(curr_block.ident()))

    # If there was no change to the entry stack, then there will be no
    # change to the exit stack; no need to do anything for this block.
    # But visit everything at least once.
    if entry_stack == curr_block.entry_stack and visited[curr_block]:
      continue

    # If executing this block would overflow the stack, skip it.
    delta = len(curr_block.delta_stack) - curr_block.delta_stack.empty_pops
    if (len(entry_stack) + delta) > memtypes.VariableStack.MAX_SIZE:
      curr_block.symbolic_overflow = True
      continue

    # Update the block's entry stack if it changed.
    curr_block.entry_stack = entry_stack.copy()

    # Construct the new exit stack from the entry stack and the stack delta

    # Build a mapping from MetaVariables to the Variables they correspond to.
    metavar_map = {}
    for var in curr_block.delta_stack:
      if isinstance(var, memtypes.MetaVariable):
        # Here we know the stack is full enough, given we already checked it,
        # but we'll get a MetaVariable if we try grabbing something off the end.
        metavar_map[var] = entry_stack.peek(var.payload)

    # Construct the exit stack itself.
    entry_stack.pop_many(curr_block.delta_stack.empty_pops)
    for var in list(curr_block.delta_stack)[::-1]:
      if isinstance(var, memtypes.MetaVariable):
        entry_stack.push(metavar_map[var])
      else:
        entry_stack.push(var)

    curr_block.exit_stack = entry_stack
    queue += curr_block.succs
    visited[curr_block] = True

  # Recondition the graph if desired, to hook up new relationships
  # possible to determine after having performed stack analysis.
  if hook_up_stack_vars:
    cfg.hook_up_stack_vars()
    cfg.apply_operations()
  if hook_up_jumps:
    cfg.hook_up_jumps()


def stack_size_analysis(cfg:cfg.ControlFlowGraph):
  """
  Determine the stack size for each basic block within the given CFG
  at both entry and exit points, if it can be known. If there are multiple
  possible stack sizes a value of BOTTOM is instead assigned.

  To calculate this information the entry point of the CFG is assigned a
  stack size of zero, and all others are given an "unknown" value, TOP.
  Then for each block, calculate its entry size by taking the meet of
  the exit sizes of its predecessors. Its own exit size is then its
  entry size plus the delta incurred by the instructions in its body.
  """

  def block_stack_delta(block:evm_cfg.EVMBasicBlock):
    """Calculate the net effect on the stack size of executing
    the instruction sequence within a block."""

    # if it's a TAC Block, then there's no need to go through the
    # EVM operations again.
    if isinstance(block, tac_cfg.TACBasicBlock):
      return len(block.stack_adds) - block.stack_pops

    delta = 0

    for op in block.evm_ops:
      delta += op.opcode.stack_delta()

    return delta

  # Stack size information per block at entry and exit points.
  entry_info = {block: lattice.IntLatticeElement.top() for block in cfg.blocks}
  exit_info = {block: lattice.IntLatticeElement.top() for block in cfg.blocks}
  block_deltas = {block: lattice.IntLatticeElement(block_stack_delta(block))
                  for block in cfg.blocks}

  # Add a distinguished empty-stack start block which does nothing.
  start_block = evm_cfg.EVMBasicBlock()
  exit_info[start_block] = lattice.IntLatticeElement(0)

  # We will initialise entry stack size of all blocks with no predecesors
  # to zero in order to reason about the stack within a connected component.
  init_blocks = ({cfg.root} if cfg.root is not None else {}) | \
                 {block for block in cfg.blocks if len(block.preds) == 0}

  for block in init_blocks:
    block.preds.append(start_block)

  # Find the fixed point that is the meet-over-paths solution
  queue = list(cfg.blocks)

  while queue:
    current = queue.pop()

    # Calculate the new entry value for the current block.
    new_entry = lattice.IntLatticeElement.meet_all([exit_info[p]
                                                   for p in current.preds])

    # If the entry value changed, we have to recompute
    # its exit value, and the entry value for its successors, eventually.
    if new_entry != entry_info[current]:
      entry_info[current] = new_entry
      exit_info[current] = new_entry + block_deltas[current]
      queue += current.succs

  # Remove the start block that was added.
  for block in init_blocks:
    block.preds.pop()

  return (entry_info, exit_info)
