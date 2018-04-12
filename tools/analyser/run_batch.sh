#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMMAND="$DIR/analyse.rb"

if [ "$#" -ne 2 ]; then
    SPEC="$DIR/../bulk_analyser/spec.dl"
else
    SPEC=$2
fi

while read f; do
    $COMMAND $SPEC $f
done < $1
