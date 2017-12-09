# BSD 3-Clause License
#
# Copyright (c) 2016, 2017, The University of Sydney. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""settings.py: dataflow analysis settings.

The user can change these settings in bin/config.ini or by providing command
line flags to override them.
Default settings are stored in src/default_config.ini.

max_iterations:
  The maximum number of graph analysis iterations.
  Lower is faster, but potentially less precise.
  A negative value means no limit. No limit by default.

bailout_seconds:
  Begin to terminate the analysis loop if it's looking to take more time
  than specified. Bailing out early may mean the analysis is not able
  to reach a fixed-point, so the results may be less precise.
  This is not a hard cap, as subsequent analysis steps are required,
  and at least one iteration will always be performed.
  A negative value means no cap on the running time.
  No cap by default.

remove_unreachable:
  Upon completion of the analysis, if there are blocks unreachable from the
  contract root, remove them. False by default.

merge_unreachable:
  Upon completion of the analysis, if there are blocks unreachable from the
  contract root, merge them. True by default.

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
  JUMPIs with known conditions become JUMPs (or are deleted).
  For example, a JUMPI with a known-true condition becomes a JUMP.
  False by default.

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
  If stacks start growing deeper without more of the program's control flow
  graph being inferred for sufficiently many iterations, we can freeze the
  maximum stack size in order to save computation.
  True by default.

clamp_stack_minimum:
  Stack sizes will not be clamped smaller than this value. Default value is 20.

widen_variables:
  If any computed variable's number of possible values exceeds a given
  threshold, widen its value to Top. True by default.

widen_threshold:
  Whenever the result of an operation may take more than this number of
  possible values, then widen the result variable's value to the Top lattice
  value (treat its value as unconstrained).
  Default value is 10.

set_valued_ops:
  If True, apply arithmetic operations to variables with multiple values;
  otherwise, only apply them to variables whose value takes only one
  value.
  Disable to gain speed at the cost of precision. True by default.

analytics:
  If True, dataflow analysis will return a dict of information about
  the contract, otherwise return an empty dict.
  Disabling this might yield a slight speed improvement. False by default.

extract_functions:
  If True, attempt to extract solidity functions.

mark_functions:
  If true, tag block names with the function(s) they belong to.

strict:
  If true, then unrecognised opcodes and invalid disassembly
  will not be skipped, but will result in an error.

Note: If we have already reached complete information about our stack CFG
structure and stack states, we can use die_on_empty_pop and reinit_stacks
to discover places where empty stack exceptions will be thrown.
"""

# The settings - these are None until initialised by import_config
max_iterations = None
bailout_seconds = None
remove_unreachable = None
merge_unreachable = None
die_on_empty_pop = None
skip_stack_on_overflow = None
reinit_stacks = None
hook_up_stack_vars = None
hook_up_jumps = None
mutate_jumps = None
generate_throws = None
final_mutate_jumps = None
final_generate_throws = None
mutate_blockwise = None
clamp_large_stacks = None
clamp_stack_minimum = None
widen_variables = None
widen_threshold = None
set_valued_ops = None
analytics = None
extract_functions = None
mark_functions = None
strict = None

# A reference to this module for retrieving its members; import sys like this so that it does not appear in _names_.
_module_ = __import__("sys").modules[__name__]

# The names of all the settings defined above.
_names_ = [s for s in dir(_module_) if not (s.startswith("_"))]

# Set up the types of the various settings, so they can be converted
# correctly when being read from config.
_types_ = {n: ("int" if n in ["max_iterations", "bailout_seconds",
                              "clamp_stack_minimum", "widen_threshold"]
else "bool") for n in _names_}

# A stack for saving and restoring setting configurations.
_stack_ = []

# Imports and definitions appearing below the definition of _names_
# do not appear in that list, by design. Don't move them up.
import logging
import sys
from os.path import dirname, normpath, join

_dir_ = dirname(__file__)

# Default settings are stored here.
_DEFAULT_LOC_ = normpath(join(_dir_, "../src/default_config.ini"))

# User settings are located here, and will override default settings.
_CONFIG_LOC_ = normpath(join(_dir_, "../bin/config.ini"))


def _get_dict_():
    """
    Return the current module's dictionary of members so the settings can be
    dynamically accessed by name.
    """
    return _module_.__dict__


def save():
    """Push the current setting configuration to the stack."""
    sd = _get_dict_()
    _stack_.append({n: sd[n] for n in _names_})


def restore():
    """Restore the setting configuration from the top of the stack."""
    _get_dict_().update(_stack_.pop())


def set_from_string(setting_name: str, value: str):
    """
    Assign to the named setting the given value, first converting that value
    to the type appropriate for that setting.
    Names and values are not case sensitive.
    """
    name = setting_name.lower()
    val = value.lower()

    if name not in _names_:
        logging.error('Unrecognised setting "%s".', setting_name)
        sys.exit(1)

    if _types_[name] == "int":
        _get_dict_()[name] = int(val)
    elif _types_[name] == "bool":
        if val in {"1", "yes", "true", "on"}:
            _get_dict_()[name] = True
        elif val in {"0", "no", "false", "off"}:
            _get_dict_()[name] = False
        else:
            logging.error('Cannot interpret value "%s" as boolean for setting "%s"',
                          value, setting_name)
            sys.exit(1)
    else:
        logging.error('Unknown type "%s" for setting "%s".', setting_name)
        sys.exit(1)


def import_config(filepath: str = _CONFIG_LOC_):
    """
    Import settings from the given configuration file.
    This should be called before running the decompiler.
    """
    import configparser
    config = configparser.ConfigParser()
    with open(_DEFAULT_LOC_) as default:
        config.read_file(default)
    config.read(filepath)
    for name in _names_:
        set_from_string(name, config.get("settings", name))
