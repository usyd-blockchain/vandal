#!/bin/bash

BATS="$( cd "$(dirname "$0")" ; pwd -P )"
FILENAME="$(basename $0)"
OUTFILE="${FILENAME%.*}"

source $BATS/environment.bash

M="disassemble:"
MP="bin/disassemble"
MPB=`basename $MP`

cat > $BATS/$OUTFILE <<EOF
#!/usr/bin/env bats

load test_helper

M="$M"

setup() {
    TEMPFILE=\`mktemp\`
}

teardown() {
    rm -f "\$TEMPFILE"
}

EOF


### Generate tests ###

cd $BATS/../../

# test disassembly of each *.hex example
for eg in $HEX_INPUT/*.hex; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg without flags" {
    run $MP -o "\$TEMPFILE" $eg
    assert_success
    run $DIFF "$EXPECTED_OUT/${MPB}_$(basename $eg).output" "\$TEMPFILE"
    assert_success
}
EOF
done

for eg in $HEX_INPUT/*.hex; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg with -p/--prettify flag" {
    run $MP -p -o "\$TEMPFILE" $eg
    assert_success
    run $DIFF "$EXPECTED_OUT/${MPB}_pretty_$(basename $eg).output" "\$TEMPFILE"
    assert_success
}
EOF
done
