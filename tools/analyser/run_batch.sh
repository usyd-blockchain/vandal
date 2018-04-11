#!/bin/bash

COMMAND="./analyse.rb"
SPEC="../bulk_analyser/spec.dl"

while read f; do
    $COMMAND $SPEC $f
done < $1
