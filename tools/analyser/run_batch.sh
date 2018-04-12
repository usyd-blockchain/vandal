#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMMAND="$DIR/analyse.rb"

if [ "$1" == "--help" ]; then
    echo "Usage: run_batch.sh CONTRACT_FILE [DATALOG_SPEC]"
    echo "Note: this script should generally only be executed by run_all.sh"
    exit 0
fi

if [ "$#" -ne 2 ]; then
    SPEC="$DIR/../bulk_analyser/spec.dl"
else
    SPEC=$2
fi

while read f; do
    $COMMAND $SPEC $f
done < $1
