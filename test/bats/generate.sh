#!/bin/bash

DIR="$( cd "$(dirname "$0")" ; pwd -P )"
cd "$DIR"

for f in ./*.generated.bats.sh; do
    bash $f
done
