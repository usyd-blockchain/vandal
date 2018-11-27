#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "Usage: analyze.sh bytecode_file datalog_file"
    exit
fi
set -x
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
\rm -rf facts-tmp
$DIR/decompile -o CALL JUMPI SSTORE SLOAD MLOAD MSTORE -d -n -t facts-tmp $1
souffle -F facts-tmp $2
\rm -rf facts-tmp
