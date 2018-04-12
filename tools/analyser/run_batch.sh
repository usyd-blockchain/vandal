#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMMAND="$DIR/analyse.rb"
SPEC="$DIR/../bulk_analyser/spec.dl"

while read f; do
    $COMMAND $SPEC $f
done < $1
