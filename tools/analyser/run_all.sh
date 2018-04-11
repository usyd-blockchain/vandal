#!/bin/bash

for f in ./batch_*.txt; do
    ./run_batch.sh $f > $f.out 2> $f.err &
done
