"""dataflow.py: fixed-point, dataflow, static analyses for CFGs"""

import time

import cfg
import evm_cfg
import tac_cfg
import lattice
import memtypes
from memtypes import VariableStack
import settings
import logger


def analyse_graph(cfg:tac_cfg.TACGraph,
                  collect_analytics:bool=False):
  """
  Infer a CFG's structure by performing dataflow analyses to resolve new edges,
  until a fixed-point, the max time or max iteration count is reached.

  Args:
      cfg: the graph to analyse; will be modified in-place.
      collect_analytics: if true, return a dict of information about the
                         contract, else return an empty dict
  """

  anal_results = {}
  if collect_analytics:
    anal_results["bailout"] = False
  bail_time = settings.bailout_seconds
  start_clock = time.clock()
  i = 0

  # Perform the stack analysis until we reach a fixed-point or a max is
  # exceeded. We alternately infer new edges that can be inferred.
  while i != settings.max_iterations:
    loop_start_clock = time.clock()
    i += 1
    modified = stack_analysis(cfg)
    modified |= cfg.clone_ambiguous_jump_blocks()
    if not modified:
      break

    # If the next analysis step will require more than the remaining time
    # or we have already exceeded our time budget, break out.
    loop_time = time.clock() - loop_start_clock
    elapsed = time.clock() - start_clock
    if bail_time >= 0:
      if elapsed > bail_time or 2*loop_time > bail_time - elapsed:
        if collect_analytics:
          anal_results["bailout"] = True
          anal_results["bail_time"] = elapsed
        break

  if collect_analytics:
      anal_results["num_clones"] = i

  # Perform a final analysis step, generating throws from invalid jumps
  cfg.hook_up_def_site_jumps()
  
  # Save the settings in order to restore them after final stack analysis
  pre_mutate_jumps = settings.mutate_jumps
  pre_generate_throws = settings.generate_throws
  
  # Perform the final analysis
  settings.mutate_jumps = settings.final_mutate_jumps
  settings.generate_throws = settings.final_generate_throws
  stack_analysis(cfg)

  # Restore settings
  settings.mutate_jumps = pre_mutate_jumps
  settings.generate_throws = pre_generate_throws

  # Collect analytics about how frequently blocks were duplicated during
  # the analysis.
  dupe_counts = {}
  if collect_analytics:
    # Find out which blocks were duplicated how many times,
    for b in cfg.blocks:
      entry = hex(b.entry)
      if entry not in dupe_counts:
        dupe_counts[entry] = 0
      else:
        dupe_counts[entry] += 1
  
  # Perform final graph manipulations, and merging any blocks that were split.
  # As well as extract jump destinations directly from def-sites if they were
  # not inferrable during previous dataflow steps.
  cfg.merge_duplicate_blocks(ignore_preds=True, ignore_succs=True)
  cfg.hook_up_def_site_jumps()
  cfg.prop_vars_between_blocks()
  cfg.make_stack_names_unique()

  # Clean up any unreachable blocks in the graph if necessary.
  if settings.remove_unreachable:
    removed = cfg.remove_unreachable_code()
    if collect_analytics:
      anal_results["unreachable_blocks"] = [b.ident() for b in removed]

  if collect_analytics:
    # accrue general graph data
    # per-block scheme: (indegree, outdegree, multiplicity)
    anal_results["num_blocks"] = len(cfg)
    block_dict = {}
    for b in cfg.blocks:
      multiplicity = dupe_counts[b.ident()] if b.ident() in dupe_counts else 0
      block_dict[b.ident()] = (len(b.preds), len(b.succs), multiplicity)
    anal_results["blocks"] = block_dict
    anal_results["funcs"] = [sig for sig in cfg.public_function_sigs() if sig is not None]

  return anal_results


def stack_analysis(cfg:tac_cfg.TACGraph) -> bool:
  """
  Determine all possible stack states at block exits. The stack size should be
  the maximum possible size, and the variables on the stack should obtain the
  maximal set of values possible at that stack position at a given point of
  program execution.

  Args:
    cfg: the graph to analyse.

  Returns:
    True iff the graph was modified.
  """

  # True iff the graph was structurally modified at some point.
  graph_modified = False

  # Initialise all entry and exit stacks to be empty.
  if settings.reinit_stacks:
    for block in cfg.blocks:
      block.symbolic_overflow = False
      block.entry_stack = VariableStack()
      block.exit_stack = VariableStack()

  # Initialise a worklist with blocks that have no precedessors
  queue = [block for block in cfg.blocks if len(block.preds) == 0]
  visited = {block: False for block in cfg.blocks}

  # The number of times any stack has changed during a step of the analysis
  # since the last time the structure of the graph was modified.
  unmod_stack_changed_count = 0
  graph_size = len(cfg.blocks)

  # Holds the join of all states this entry stack has ever been in.
  cumulative_entry_stacks = {block.ident(): VariableStack()
                             for block in cfg.blocks}

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
    if curr_block.build_exit_stack():
      continue

    if settings.mutate_blockwise:
      # Hook up edges from the changed stack after each block has been handled,
      # rather than all at once at the end. The graph evolves as we go.

      if settings.hook_up_stack_vars:
        curr_block.hook_up_stack_vars()
        curr_block.apply_operations(settings.set_valued_ops)

      if settings.hook_up_jumps:
        old_succs = list(curr_block.succs)
        modified = curr_block.hook_up_jumps()
        graph_modified |= modified

        if modified:
          # Some successors of a modified block may need to be rechecked.
          queue += [s for s in old_succs if s not in queue]

          if settings.widen_variables:
            cumulative_entry_stacks = {block.ident(): VariableStack()
                                       for block in cfg.blocks}
          if settings.clamp_large_stacks:
            unmod_stack_changed_count = 0
            for succ in curr_block.succs:
              visited[succ] = False

    if settings.widen_variables:
      # If a variable's possible value set might be practically unbounded,
      # it must be widened in order for our analysis not to take forever.
      # Additionally, the widening threshold should be set low enough that
      # computations involving those large stack variables don't take too long.

      cume_stack = cumulative_entry_stacks[curr_block.ident()]
      cumulative_entry_stacks[curr_block.ident()] = VariableStack.join(cume_stack,
                                                        curr_block.entry_stack)

      # Check for each stack variable whether it needs widening.
      for i in range(len(cume_stack)):
        v = cume_stack.value[i]

        if len(v) > settings.widen_threshold:
          logger.log("Widening {} in block {}"
                     .format(curr_block.entry_stack.value[i].identifier,
                             curr_block.ident()))
          logger.log("  Accumulated values: {}".format(cume_stack.value[i]))
          cume_stack.value[i] = memtypes.Variable.top()
          curr_block.entry_stack.value[i].value = cume_stack.value[i].value

    if settings.clamp_large_stacks:
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
        # clamp all stacks at their current sizes, if they are large enough.
        for b in cfg.blocks:
          new_size = max(len(b.entry_stack), len(b.exit_stack))
          if new_size >= settings.clamp_stack_minimum:
            b.entry_stack.set_max_size(new_size)
            b.exit_stack.set_max_size(new_size)

    queue += [s for s in curr_block.succs if s not in queue]
    visited[curr_block] = True

  # Recondition the graph if desired, to hook up new relationships
  # possible to determine after having performed stack analysis.
  if settings.hook_up_stack_vars:
    cfg.hook_up_stack_vars()
    cfg.apply_operations()
  if settings.hook_up_jumps:
    graph_modified |= cfg.hook_up_jumps()
    graph_modified |= cfg.add_missing_split_edges()

  return graph_modified


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
