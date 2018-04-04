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

"""function.py:
Classes for identifying and exporting functions in the control flow graph.
Tested and developed on Solidity version 0.4.11"""

import typing as t

import src.memtypes as memtypes
import src.opcodes as opcodes
import src.tac_cfg as tac_cfg


class Function:
    """
    A representation of a Solidity function with associated metadata.
    """

    def __init__(self):
        self.body = []
        self.start_block = None
        self.end_block = None
        self.mapping = {}  # a mapping of preds to succs of the function body.
        self.signature = ""
        self.is_private = False

    def __str__(self):
        if self.is_private:
            sig = "Private function"
        else:
            if self.signature:
                sig = "Public function signature: " + self.signature
            else:
                sig = "Public fallback function"
        entry_block = "Entry block: " + self.start_block.ident()
        if self.end_block is not None:
            exit_block = "Exit block: " + self.end_block.ident()
        else:
            exit_block = "Exit block: None identified"
        body = "Body: " + ", ".join(b.ident() for b in sorted(self.body))
        return "\n".join([sig, entry_block, exit_block, body])


class FunctionExtractor:
    """A class for extracting Solidity functions from an already generated TAC cfg."""

    def __init__(self, cfg: tac_cfg.TACGraph):
        self.cfg = cfg  # the tac_cfg that this operates on
        self.public_functions = []
        self.private_functions = []
        self.invoc_pairs = {}  # a mapping from invocation sites to return addresses

    def __str__(self) -> str:
        """
        Returns a string representation of all the functions in the graph
        after extraction has been performed.

        Returns:
          A string summary of all the functions in the control flow graph
        """

        return "\n".join(["Function {}:\n{}\n".format(str(i), str(func))
                          for i, func in enumerate(self.functions)])

    @staticmethod
    def mark_body(path: t.List[tac_cfg.TACBasicBlock], num: int) -> None:
        """
        Marks every block in the path with the given number.
        Used for marking function bodies.
        """
        for block in path:
            block.ident_suffix += "_F" + str(num)

    @property
    def functions(self):
        return self.public_functions + self.private_functions

    def extract(self) -> None:
        """Extracts private and public functions"""
        self.private_functions.extend(self.extract_private_functions())
        self.public_functions.extend(self.extract_public_functions())

    def mark_functions(self) -> None:
        """Mark extracted function bodies with unique identifier suffixes."""
        for i, func in enumerate(self.functions):
            self.mark_body(func.body, i)

    def extract_public_functions(self) -> t.Iterable[Function]:
        """
        Return a list of the solidity public functions exposed by the contract of this cfg.

        Returns:
          A list of the extracted functions.
        """

        # Find the function signature variable holding call data 0,
        # at the earliest query to that location in the program.
        load_list = []
        load_block = None

        for block in sorted(self.cfg.blocks):
            load_list = [op for op in block.tac_ops
                         if op.opcode == opcodes.CALLDATALOAD
                         and op.args[0].value.const_value == 0]
            if len(load_list) != 0:
                load_block = block
                break

        if len(load_list) == 0:
            return []
        sig_var = load_list[0].lhs

        # Follow the signature until it's transformed into its final shape.
        for o in load_block.tac_ops:
            if not isinstance(o, tac_cfg.TACAssignOp) or id(sig_var) not in [id(a.value) for a in o.args]:
                continue
            if o.opcode == opcodes.EQ:
                break
            sig_var = o.lhs

        # Find all the places the function signature is compared to a constant
        func_sigs = []
        fallthroughs = []

        for b in self.cfg.blocks:
            for o in b.tac_ops:
                if not isinstance(o, tac_cfg.TACAssignOp) or id(sig_var) not in [id(a.value) for a in o.args]:
                    continue
                if o.opcode == opcodes.EQ:
                    sig = [a.value for a in o.args if id(a.value) != id(sig_var)][0]

                    # Append the non-fallthrough successor to the function sig list
                    for succ in [s for s in b.succs if s != b.fallthrough]:
                        func_sigs.append((succ, hex(sig.const_value)))

                    # Save the fallthrough location so the last one can be added as
                    # the fallback function
                    if b.fallthrough is not None:
                        fallthroughs.append(b.fallthrough)

        # Add the fallback function
        if fallthroughs:
            func_sigs.append((fallthroughs[-1], ""))

        return [self.get_public_function(s[0], signature=s[1]) for s in func_sigs]

    def get_public_function(self, block: tac_cfg.TACBasicBlock,
                            signature: str = "") -> Function:
        """
        Identifies the function starting with the given block

        Args:
          block: A BasicBlock to be used as the starting block for the function.
          signature: The solidity hashed function signature associated with the function to be extracted.

        Returns:
          A Function object containing the blocks composing the function body.
        """
        body = []
        queue = [block]
        end_block = None
        cur_block = None  # A placeholder for prev_block
        jump = False  # Keeps track of whether we have just jumped or not
        pre_jump_block = block
        while len(queue) > 0:
            prev_block = cur_block
            cur_block = queue.pop(0)

            # jump over function bodies
            for f in self.functions:
                if cur_block in f.body and not jump:
                    cur_block = self.__jump_to_next_loc(cur_block, body,
                                                        prev_block.exit_stack)
                if cur_block in f.body and jump:
                    # If we jumped, the previous block is actually from before the jump
                    cur_block = self.__jump_to_next_loc(cur_block, body,
                                                        pre_jump_block.exit_stack)
                    jump = False
            # In case we didn't find a new block to jump to
            if cur_block is None:
                continue
            # Jump over other invocation sites after adding them to body
            if cur_block in self.invoc_pairs:
                jump = True
                pre_jump_block = cur_block
                if cur_block not in body:
                    body.append(cur_block)
                cur_block = self.invoc_pairs[cur_block]
            # Since an invocation site always has a successor,
            # it can't be an end block for the function

            if len(cur_block.succs) == 0:
                end_block = cur_block
            if cur_block not in body:
                body.append(cur_block)
                for b in cur_block.succs:
                    queue.append(b)
        f = Function()
        f.body = body
        f.start_block = block
        # Assuming that there will only be one end_block
        f.end_block = end_block
        f.signature = signature
        f.is_private = False
        return f

    def __jump_to_next_loc(self, block: tac_cfg.TACBasicBlock,
                           body: t.List[tac_cfg.TACBasicBlock],
                           exit_stack: memtypes.VariableStack) -> tac_cfg.TACBasicBlock:
        """
        Helper method to jump over private functions during public function
        identification. Uses BFS to find the next available block that is not
        in a function.

        Args:
          block: The current block to be tested as being in the function body
          body: The body of the current function being identified.
          exit_stack: The stack of the previous block, or block before that after
                      a previous jump over a function. If a block is in this
                      exit_stack, then it is the next block in the flow of the
                      function currently being identified.
        """
        queue = [block]
        visited = [block]
        while len(queue) > 0:
            block = queue.pop()
            if len(block.succs) == 0:
                return block
            visited.append(block)
            in_func = False
            for f in self.functions:
                if block in f.body:
                    in_func = True
                    break
            # Check that the block is not related to another function,
            # and we haven't visited it yet, and that it is in the exit stack
            # We can discard blocks in the body of the function being identified
            # since we want to discover new blocks, not old ones
            if not in_func and block not in self.invoc_pairs.keys() and \
                block.ident() in str(exit_stack) and block not in body:
                return block
            for succ in block.succs:
                if succ not in visited:
                    queue.append(succ)
        return None

    def extract_private_functions(self) -> t.List[tac_cfg.TACBasicBlock]:
        """
        Extracts private functions

         Returns:
          A list of of Function objects: the private functions identified in the cfg
        """
        # Get invocation site -> return block mappings
        start_blocks = []
        pair_list = []
        for block in reversed(self.cfg.blocks):
            invoc_pairs = self.is_private_func_start(block)
            if invoc_pairs:
                start_blocks.append(block)
                pair_list.append(invoc_pairs)

        # Store invocation site - return pairs for later usage
        for d in pair_list:
            for key in d.keys():
                self.invoc_pairs[key] = d[key]

        # Find the Function body itself
        private_funcs = list()
        for i, block in enumerate(start_blocks):
            return_blocks = list(pair_list[i].values())
            f = self.find_func_body(block, return_blocks, pair_list)
            if not f or len(f.body) == 1:  # Can't have a function with 1 block in EVM
                continue
            if f is not None:
                f.is_private = True
                private_funcs.append(f)
        return private_funcs

    def is_private_func_start(self, block: tac_cfg.TACBasicBlock) -> t.Dict[
        tac_cfg.TACBasicBlock, tac_cfg.TACBasicBlock]:
        """
        Determines the invocation and return points of the function beginning
        with the given block, if it exists.

        Args:
          block: a BasicBlock to be tested as the possible beginning of a function

        Returns:
          A mapping of invocation sites to return blocks of the function,
          if the given block is the start of a function.
          None if the block is not the beginning of a function.
        """
        # if there are multiple paths converging, this is a possible function start
        preds = list(sorted(block.preds))
        if (len(preds) <= 1) or len(list(block.succs)) == 0:
            return None
        func_succs = []  # a list of what succs to look out for.
        func_mapping = {}  # mapping of predecessors -> successors of function
        params = []  # list of parameters
        for pre in preds:
            if pre not in block.succs:
                # Check for at least 2 push opcodes and net stack gain
                push_count = 0
                for evm_op in pre.evm_ops:
                    if evm_op.opcode.is_push():
                        push_count += 1
                if push_count <= 1:
                    return None
                if len(pre.delta_stack) == 0:
                    return None
                for val in list(pre.delta_stack):
                    ref_block = self.cfg.get_block_by_ident(str(val))
                    # Ensure that the block pointed to by the block exists and is reachable
                    if ref_block is not None and self.cfg.reaches(pre, [ref_block]):
                        func_mapping[pre] = ref_block
                        func_succs.append(ref_block)
                        break
                    params.append(val)
        if not func_succs or len(func_mapping) == 1:
            return None
        # We have our start
        return func_mapping

    def find_func_body(self, block: tac_cfg.TACBasicBlock,
                       return_blocks: t.List[tac_cfg.TACBasicBlock],
                       invoc_pairs: t.List[tac_cfg.TACBasicBlock]) -> 'Function':
        """
        Assuming the block is a definite function start, identifies all paths
        from start to end using BFS

        Args:
          block: the start block of a function.
          return_blocks: the list of return blocks of the function.
          invoc_pairs: a mapping of all other invocation and return point pairs
                       to allow jumping over other functions.

        Returns:
          A function object representing the function starting with the given block
        """
        # Traverse down levels with BFS until we hit a block that has the return
        # addresses specified above
        body = []
        queue = [block]
        end = False
        while len(queue) > 0:
            curr_block = queue.pop(0)
            # When we call a function, we just jump to the return address
            for entry in invoc_pairs:
                if curr_block in entry:
                    body.append(curr_block)
                    curr_block = entry[curr_block]
            cur_succs = [b for b in curr_block.succs]
            if set(return_blocks).issubset(set(cur_succs)):
                end = True
            if curr_block not in body and self.cfg.reaches(curr_block, return_blocks):
                body.append(curr_block)
                for b in curr_block.succs:
                    if b not in return_blocks:
                        queue.append(b)

        if end:
            f = Function()
            f.start_block = block
            poss_exit_blocks = [sorted(b.preds) for b in return_blocks]
            exit_blocks = set(poss_exit_blocks[0])
            for preds in poss_exit_blocks:
                exit_blocks = exit_blocks & set(preds)
            # We assume the end_block is the last block in the disasm from all candidates
            f.end_block = sorted(exit_blocks).pop()
            f.succs = sorted(return_blocks)
            f.preds = sorted(block.preds)
            f.body = body
            return f

        return None
