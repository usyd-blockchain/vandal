"""dataflow.py: fixed-point, dataflow, static analyses for CFGs"""

import cfg
import evm_cfg
import tac_cfg
import lattice
import memtypes
from memtypes import VariableStack as VStack
from memtypes import MetaVariable as MetaVar
import exporter

def stack_analysis(cfg:tac_cfg.TACGraph,
                   die_on_empty_pop:bool=False, reinit_stacks:bool=True,
                   hook_up_stack_vars:bool=True, hook_up_jumps:bool=True,
                   mutate_jumps:bool=False, generate_throws:bool=False,
                   mutate_blockwise:bool=True, clamp_large_stacks:bool=True,
                   widen_large_variables:bool=True) -> None:
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
    mutate_jumps: JUMPIs with known conditions become JUMPs (or are deleted)
    generate_throws: JUMP and JUMPI instructions with invalid destinations
                     become THROW and THROWIs
    mutate_blockwise: hook up stack vars and/or hook up jumps after each block
                      rather than after the whole analysis is complete.
    clamp_large_stacks: if stacks start growing without bound, reduce the stack
                        size in order to hasten convergence.
    widen_large_variables: if any stack variable's number of possible values
                           exceeds a given threshold, widen its value to Top.

  If we have already reached complete information about our stack CFG structure
  and stack states, we can use die_on_empty_pop and reinit_stacks to discover
  places where empty stack exceptions will be thrown.
  """

  # Initialise all entry and exit stacks to be empty.
  if reinit_stacks:
    for block in cfg.blocks:
      block.symbolic_overflow = False
      block.entry_stack = VStack()
      block.exit_stack = VStack()

  # Initialise a worklist with blocks that have no precedessors
  queue = [block for block in cfg.blocks if len(block.preds) == 0]
  visited = {block: False for block in cfg.blocks}

  # The number of times any stack has changed during a step of the analysis
  # since the last time the structure of the graph was modified.
  unmod_stack_changed_count = 0
  graph_size = len(cfg.blocks)

  # Holds the join of all states this entry stack has ever been in.
  cumulative_entry_stacks = {block.ident(): VStack() for block in cfg.blocks}
  # Widen if the size of a given variable exceeds this threshold
  widen_threshold = 20

  # Churn until we reach a fixed point.
  while queue:
    curr_block = queue.pop(0)

    # If there was no change to the entry stack, then there will be no
    # change to the exit stack; no need to do anything for this block.
    # But visit everything at least once.
    if not curr_block.build_entry_stack() and visited[curr_block]:
      continue

    # If a symbolic overflow occurred, the exit stack did not change,
    # and we can similarly skip the rest of the processing.
    if curr_block.build_exit_stack(die_on_empty_pop=die_on_empty_pop):
      continue

    if mutate_blockwise:
      # Hook up edges from the changed stack after each block has been handled,
      # rather than all at once at the end. The graph evolves as we go.

      if hook_up_stack_vars:
        curr_block.hook_up_stack_vars()
        curr_block.apply_operations()

      if hook_up_jumps:
        old_succs = list(curr_block.succs)
        modified = curr_block.hook_up_jumps(mutate_jumps=mutate_jumps,
                                            generate_throws=generate_throws)
        if modified:
          # Some successors of a modified block may need to be rechecked.
          queue += [s for s in old_succs if s not in queue]

          if widen_large_variables:
            cumulative_entry_stacks = {block.ident(): VStack() for block in cfg.blocks}
          if clamp_large_stacks:
            unmod_stack_changed_count = 0
            for succ in curr_block.succs:
              visited[succ] = False

    if widen_large_variables:
      # If a variable's possible value set might be practically unbounded,
      # it must be widened in order for our analysis not to take forever.
      # Additionally, the widening threshold should be set low enough that
      # computations involving those large stack variables don't take too long.

      cume_stack = cumulative_entry_stacks[curr_block.ident()]
      cumulative_entry_stacks[curr_block.ident()] = VStack.join(cume_stack,
                                                        curr_block.entry_stack)

      # Check for each stack variable whether it needs widening.
      for i in range(len(cume_stack)):
        v = cume_stack.value[i]

        if len(v) > widen_threshold:
          print("Widening {} in block {}"
                .format(curr_block.entry_stack.value[i], curr_block.ident()))
          print("  Accumulated values: {}".format(cume_stack.value[i]))
          cume_stack.value[i] = memtypes.Variable.top()
          curr_block.entry_stack.value[i].value = cume_stack.value[i].value

    if clamp_large_stacks:
      # As variables can grow in size, stacks can grow in depth.
      # If a stack is getting unmanageably deep, we may choose to freeze its
      # maximum depth at some point.
      # If graph_size visited blocks change their stack states without
      # the structure of the graph being changed, then we assume there is a
      # positive cycle that will overflow the stacks. Clamp max stack size to
      # current maximum in response.

      if visited[curr_block]:
        unmod_stack_changed_count += 1

      if unmod_stack_changed_count > graph_size:
        # clamp all stacks at their current sizes
        for b in cfg.blocks:
          new_size = max(len(b.entry_stack), len(b.exit_stack))
          b.entry_stack.set_max_size(new_size)
          b.exit_stack.set_max_size(new_size)

    queue += [s for s in curr_block.succs if s not in queue]
    visited[curr_block] = True

  # Recondition the graph if desired, to hook up new relationships
  # possible to determine after having performed stack analysis.
  if hook_up_stack_vars:
    cfg.hook_up_stack_vars()
    cfg.apply_operations()
  if hook_up_jumps:
    cfg.hook_up_jumps(mutate_jumps=mutate_jumps,
                      generate_throws=generate_throws)
    cfg.add_missing_split_edges()


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
