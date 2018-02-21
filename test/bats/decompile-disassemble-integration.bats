#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="disassemble|decompile (integration):"

# module path
DECOMP="bin/decompile"
DISASM="bin/disassemble"

setup() {
    TEMPFILE1=`mktemp`
    TEMPFILE2=`mktemp`
}

teardown() {
    rm -f "$TEMPFILE1" "$TEMPFILE2"
}

# test decompilation of *.hex example
@test "$M $HEX_INPUT/dao_hack.hex disassemble output as decompile input" {
    run $DISASM -o "$TEMPFILE1" $HEX_INPUT/dao_hack.hex
    assert_success
    run $DECOMP -a "$TEMPFILE1" "$TEMPFILE2"
    assert_success
    run $DIFF "$EXPECTED_OUT/decompile_dao_hack.hex.output" "$TEMPFILE2"
    assert_success
}
