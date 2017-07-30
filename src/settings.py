"""settings.py: dataflow analysis settings.

max_iterations:
  The maximum number of times to perform the graph analysis step.
  A negative value means no maximum. No limit by default.

bailout_seconds:
  Break out of the analysis loop if the time spent exceeds this value.
  Not a hard cap as subsequent analysis steps are required, and at least one
  iteration will always be performed. A negative value means no maximum.
  No limit by default.

remove_unreachable:
  Upon completion of the analysis, if there are blocks unreachable from the
  contract root, remove them. False by default.

die_on_empty_pop:
  Raise an exception if an empty stack is popped. False by default.

skip_stack_on_overflow:
  Do not apply changes to exit stacks after a symbolic overflow occurrs
  in their blocks. True by default.

reinit_stacks:
  Reinitialise all blocks' exit stacks to be empty. True by default.

hook_up_stack_vars:
  After completing the analysis, propagate entry stack values into blocks.
  True by default.

hook_up_jumps:
  Connect any new edges that can be inferred after performing the analysis.
  True by default.

mutate_jumps:
  JUMPIs with known conditions become JUMPs (or are deleted). False by default.

generate_throws:
  JUMP and JUMPI instructions with invalid destinations become THROW and
  THROWIs. False by default.

final_mutate_jumps:
  Mutate jumps in the final analysis phase. False by default.

final_generate_throws:
  generate throws in the final analysis phase. True by default.

mutate_blockwise:
  Hook up stack vars and/or hook up jumps after each block rather than after
  the whole analysis is complete. True by default.

clamp_large_stacks:
  If stacks start growing without bound, reduce the maximum stack size in order
  to hasten convergence. True by default.

clamp_stack_minimum:
  Stack sizes will not be clamped smaller than this value. Default value is 20.

widen_variables:
  If any stack variable's number of possible values exceeds a given threshold,
  widen its value to Top. True by default.

widen_threshold:
  Widen if the size of a given variable exceeds this value.
  Default value is 20.

set_valued_ops:
  If true, apply arithmetic operations to variables with multiple values;
  otherwise, only apply them to variables whose value is definite.
  False by default.

Note: If we have already reached complete information about our stack CFG
structure and stack states, we can use die_on_empty_pop and reinit_stacks
to discover places where empty stack exceptions will be thrown.
"""

# The settings

max_iterations         = -1
bailout_seconds        = -1
remove_unreachable     = False
die_on_empty_pop       = False
skip_stack_on_overflow = True
reinit_stacks          = True
hook_up_stack_vars     = True
hook_up_jumps          = True
mutate_jumps           = False
generate_throws        = False
final_mutate_jumps     = False
final_generate_throws  = True
mutate_blockwise       = True
clamp_large_stacks     = True
clamp_stack_minimum    = 20
widen_variables        = True
widen_threshold        = 20
set_valued_ops         = False


# A reference to this module for retrieving its members; import sys like this so that it does not appear in _names_.
_module_ = __import__("sys").modules[__name__]

# The names of all the settings defined above.
_names_ = [s for s in dir(_module_) if not (s.startswith("_"))]

# A stack for saving and restoring setting configurations.
_stack_ = []

def _get_dict_():
  """Return the current module's dictionary of members so the settings can be dynamically accessed by name."""
  return _module_.__dict__

def save():
  """Push the current setting configuration to the stack."""
  sd = _get_dict_()
  _stack_.append({n: sd[n] for n in _names_})

def restore():
  """Restore the setting configuration from the top of the stack."""
  _get_dict_().update(_stack_.pop())
