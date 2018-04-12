#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RUN_BATCH="$DIR/run_batch.sh"

if [ "$#" -ne 1 ]; then
    SPEC=""
else
    SPEC="$1"
fi

for f in ./batch_*.txt; do
    $RUN_BATCH $f $SPEC > $f.out 2> $f.err &
done
