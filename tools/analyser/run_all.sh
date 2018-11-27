#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RUN_BATCH="$DIR/run_batch.sh"

if [ "$1" == "--help" ]; then
    echo "Usage: run_all.sh [DATALOG_SPEC]"
    exit 0
fi

if [ "$#" -ne 1 ]; then
    SPEC=""
else
    SPEC="$1"
fi

for f in ./batch_*.txt; do
    $RUN_BATCH $f $SPEC > $f.out 2> $f.err &
done
