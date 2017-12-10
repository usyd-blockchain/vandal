#!/bin/bash

BATS="$( cd "$(dirname "$0")" ; pwd -P )"
FILENAME="$(basename $0)"
OUTFILE="${FILENAME%.*}"

source $BATS/environment.bash

M="decompile:"
MP="bin/decompile"
MPB=`basename $MP`

cat > $BATS/$OUTFILE <<EOF
#!/usr/bin/env bats

load test_helper

M="$M"

EOF


### Generate tests ###

cd $BATS/../../

# test decompilation of each *.dasm file
for eg in $DASM_INPUT/*.dasm; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg with -a/--disassembly flag" {
    run $MP --disassembly $eg
    assert_success
    assert_output < "$EXPECTED_OUT/${MPB}_$(basename $eg).output"
    run $MP -a $eg
    assert_success
    assert_output < "$EXPECTED_OUT/${MPB}_$(basename $eg).output"
}

EOF
done

# test failed decompilation of each *.dasm
for eg in $DASM_INPUT/*.dasm; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg fails without -a/--disassembly flag" {
    run $MP $eg
    assert_failure
}

EOF
done

# test decompilation of each *.hex example
for eg in $HEX_INPUT/*.hex; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg without flags" {
    run $MP $eg
    assert_success
    assert_output < "$EXPECTED_OUT/${MPB}_$(basename $eg).output"
}

EOF
done

for eg in $HEX_INPUT/*.hex; do
cat >> $BATS/$OUTFILE <<EOF
@test "$M $eg with -b/--bytecode flag" {
    run $MP -b $eg
    assert_success
    assert_output < "$EXPECTED_OUT/${MPB}_$(basename $eg).output"
    run $MP --bytecode $eg
    assert_success
    assert_output < "$EXPECTED_OUT/${MPB}_$(basename $eg).output"
}

EOF
done
