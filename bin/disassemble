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

# Standard lib imports
import argparse
import logging
import sys
import traceback
from os.path import abspath, dirname, join

# Prepend .. to $PATH so the project modules can be imported below
src_path = join(dirname(abspath(__file__)), "..")
sys.path.insert(0, src_path)

# Local project imports
import src.opcodes as opcodes
import src.blockparse as blockparse
import src.settings as settings

# Colour scheme for prettified output
# See: https://pypi.python.org/pypi/termcolor
PC_COL       = "white"
OP_COL       = "cyan"
OP_HALT_COL  = "red"
OP_FLOW_COL  = "magenta"
OP_JDEST_COL = "green"
VAL_COL      = "yellow"
COMMENT_COL  = "white"

# Configure argparse
parser = argparse.ArgumentParser(description="An EVM bytecode disassembler")

parser.add_argument("-p",
                    "--prettify",
                    action="store_true",
                    default=False,
                    help="colourize the disassembly and separate block "
                         "boundaries with a newline")

parser.add_argument("-s",
                    "--strict",
                    action="store_true",
                    default=False,
                    help="halt and produce no output when malformed "
                         "input is given")

parser.add_argument("-o",
                    "--outfile",
                    type=argparse.FileType("w"),
                    default=sys.stdout,
                    help="file to which decompiler output should be written "
                         "(stdout by default).")

parser.add_argument("-v",
                    "--verbose",
                    action="store_true",
                    help="emit verbose debug output to stderr.")

parser.add_argument("-vv",
                    "--prolix",
                    action="store_true",
                    help="emit debug output to stderr at higher verbosity "
                         "level.")

parser.add_argument("infile",
                    nargs="*",
                    type=argparse.FileType("r"),
                    default=sys.stdin,
                    help="file from which decompiler input should be read "
                         "(stdin by default).")

# Parse the arguments.
args = parser.parse_args()

# Set up logger, with appropriate log level depending on verbosity.
log_level = logging.WARNING
if args.prolix:
  log_level = logging.DEBUG
elif args.verbose:
  log_level = logging.INFO
logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

if args.prettify:
  from termcolor import colored

# Initialise settings.
settings.import_config(settings._CONFIG_LOC_)
settings.strict = args.strict

def format_pc(pc):
  pc = "0x{:02x}".format(pc)
  if args.prettify:
    pc = colored(pc, PC_COL)
  return pc


def format_opcode(opcode):
  op = "{:<6}".format(opcode.name)
  if args.prettify:
    if opcode.halts():
      op = colored(op, OP_HALT_COL)
    elif opcode.alters_flow():
      op = colored(op, OP_FLOW_COL)
    elif opcode == opcodes.JUMPDEST:
      op = colored(op, OP_JDEST_COL)
    else:
      op = colored(op, OP_COL)
  return op


def format_value(value):
  if value is None:
    return str()
  value = "0x{:02x}".format(value)
  if args.prettify:
    value = colored(value, VAL_COL)
  return value


try:
  for i, infile in enumerate(args.infile):
    if hasattr(infile, 'name'):
      logging.info("Processing %s", infile.name)

    # for multiple input files, comment above each output with the
    # path of its file
    if hasattr(args.infile, '__len__') and len(args.infile) > 1:
      fname_comment = "; Disassembly from\n;  {}\n".format(infile.name)
      if args.prettify:
        fname_comment = colored(fname_comment, COMMENT_COL,
                                attrs=['dark'])
      print(fname_comment, file=args.outfile)

    # join the bytecode all into one string
    bytecode = ''.join(l.strip() for l in infile if len(l.strip()) > 0)

    # parse bytecode and create basic blocks
    blocks = blockparse.EVMBytecodeParser(bytecode).parse()

    # Print disassembly from each block
    for b in blocks:
      for op in b.evm_ops:
        print(format_pc(op.pc),
              format_opcode(op.opcode),
              format_value(op.value),
              file=args.outfile)

      if args.prettify:
        print("", file=args.outfile)

    # for multiple input files, separate output of each file with a newline
    if hasattr(args.infile, '__len__') and i + 1 < len(args.infile):
      print("", file=args.outfile)

# ValueError happens with invalid hexadecimal
except ValueError as e:
  logging.exception("Problem while disassembling.")
  sys.exit(1)

# LookupError happens with invalid opcodes
except LookupError as e:
  if settings.strict:
    logging.exception("Invalid opcode during disassembly (strict).")
    sys.exit(1)
  else:
    logging.debug(traceback.format_exc())

# Catch a Control-C and exit with UNIX failure status 1
except KeyboardInterrupt:
  logging.info(traceback.format_exc())
  logging.error("\nInterrupted by user")
  sys.exit(1)
