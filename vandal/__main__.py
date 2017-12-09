#!/usr/bin/env python

from argparse import ArgumentParser
from sys import modules

from vandal.__init__ import __version__
import vandal.cli.decompile as decompile


def _build_parser():
    """
    Build argparse parser object

    :returns argparse parser object
    :rtype ArgumentParser
    """
    parser = ArgumentParser(description="Ethereum VM bytecode decompiler")

    subparsers = parser.add_subparsers(help='disassemble and decompile')

    decompile_sub = subparsers.add_parser('decompile', help=decompile.__desc__)
    decompile.build_decompile_parser(decompile_sub)

    parser.add_argument('--version', action='version',
                        version='{} {}'.format(modules[__name__].__package__, __version__))
    return parser


if __name__ == '__main__':
    print(dict(_build_parser().parse_args()._get_kwargs()))
