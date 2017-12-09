#!/usr/bin/env python3

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

"""convert.py: read runtime bytecode and produce contract creation bytecode."""

import sys


def hexify(number):
    """Produce hex string of the given number with leading '0x' removed."""
    return hex(number)[2:]


def lenhexbytify(string):
    """Length of input string as a hex string with a leading zero if length string length is odd."""
    out_str = hexify(len(string) // 2)
    return ("0" if len(out_str) % 2 else "") + out_str


if len(sys.argv) > 1:
    print("No args please; reads runtime bytecode from stdin, writes creation bytecode to stdout.")
else:
    runtime = input().strip()
    len_str = lenhexbytify(runtime)
    push_code = hexify(0x60 + len(len_str) // 2 - 1)
    init_str = "34600057{}{}60008160".format(push_code, len_str)
    post_str = "8239f3"

    len_str = lenhexbytify(init_str + lenhexbytify(init_str) + post_str)
    new_len_str = lenhexbytify(init_str + len_str + post_str)
    while new_len_str != len_str:
        len_str = lenhexbytify(init_str + new_len_str + post_str)
        new_len_str = lenhexbytify(init_str + len_str + post_str)

    print(init_str + len_str + post_str + runtime)
