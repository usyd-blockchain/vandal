#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RUN_BATCH="$DIR/run_batch.sh"

for f in ./batch_*.txt; do
    $RUN_BATCH $f > $f.out 2> $f.err &
done
