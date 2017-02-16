#!/usr/bin/env python3
"""convert.py: read runtime bytecode and produce contract creation bytecode."""

import sys

def hexify(number):
  """Produce hex string of the given number with leading '0x' removed."""
  return hex(number)[2:]

def lenhexbytify(string):
  """Length of input string as a hex string with a leading zero if length string length is odd."""
  out_str = hexify(len(string) // 2)
  return ("0" if len(out_str)%2 else "") + out_str

if len(sys.argv) > 1:
  print("No args please; reads runtime bytecode from stdin, writes creation bytecode to stdout.")
else:
  runtime = input().strip()
  len_str = lenhexbytify(runtime)
  push_code = hexify(0x60 + len(len_str)//2 - 1)
  init_str = "34600057{}{}60008160".format(push_code, len_str)
  post_str = "8239f3"

  len_str = lenhexbytify(init_str + lenhexbytify(init_str) + post_str)
  new_len_str = lenhexbytify(init_str + len_str + post_str)
  while new_len_str != len_str:
    len_str = lenhexbytify(init_str + new_len_str + post_str)
    new_len_str = lenhexbytify(init_str + len_str + post_str)

  print(init_str + len_str + post_str + runtime)
