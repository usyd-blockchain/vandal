"""settings.py: dataflow analysis settings.

Note: If we have already reached complete information about our stack CFG
structure and stack states, we can use die_on_empty_pop and reinit_stacks
to discover places where empty stack exceptions will be thrown.
"""

max_iterations:int=-1
"""
The maximum number of times to perform the graph analysis step. 
A negative value means no maximum.
"""

bailout_seconds:int=-1
"""
Break out of the analysis loop if the time spent exceeds this value. 
Not a hard cap as subsequent analysis steps are required, and at least one
iteration will always be performed. A negative value means no maximum.
"""

remove_unreachable:bool=False
"""
Upon completion of the analysis, if there are blocks unreachable from the
contract root, remove them.
"""

die_on_empty_pop:bool=False
"""Raise an exception if an empty stack is popped."""

skip_stack_on_overflow:bool=True
"""
Do not apply changes to exit stacks after a symbolic overflow occurrs
in their blocks.
"""

reinit_stacks:bool=True
"""Reinitialise all blocks' exit stacks to be empty."""

hook_up_stack_vars:bool=True
"""After completing the analysis, propagate entry stack values into blocks."""

hook_up_jumps:bool=True
"""Connect any new edges that can be inferred after performing the analysis."""

mutate_jumps:bool=False
"""JUMPIs with known conditions become JUMPs (or are deleted)."""

generate_throws:bool=False
"""
JUMP and JUMPI instructions with invalid destinations become THROW
and THROWIs.
"""

final_mutate_jumps:bool=False
"""Mutate jumps in the final analysis phase."""

final_generate_throws:bool=True
"""generate throws in the final analysis phase."""

mutate_blockwise:bool=True
"""
Hook up stack vars and/or hook up jumps after each block rather than after
the whole analysis is complete.
"""

clamp_large_stacks:bool=True
"""
If stacks start growing without bound, reduce the maximum stack size in order
to hasten convergence.
"""

clamp_stack_minimum:int=20
"""Stack sizes will not be clamped smaller than this value."""

widen_variables:bool=True
"""
If any stack variable's number of possible values exceeds a given threshold,
widen its value to Top.
"""

widen_threshold:int=20
"""Widen if the size of a given variable exceeds this value."""

set_valued_ops:bool=False
"""
If true, apply arithmetic operations to variables with multiple values;
otherwise, only apply them to variables whose value is definite.
"""
