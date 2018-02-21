#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="disassemble | decompile (integration tests):"

# module path
DECOMP="bin/decompile"
DISASM="bin/disassemble"

# test decompilation of *.hex example
TEMPFILE1=`mktemp`
TEMPFILE2=`mktemp`
@test "$M testing usage of disassembler output as decompiler input using $HEX_INPUT/dao_hack.hex" {
    run $DISASM -o "$TEMPFILE1" $HEX_INPUT/dao_hack.hex
    assert_success
    run $DECOMP -a "$TEMPFILE1" "$TEMPFILE2"
    assert_success
    run $DIFF "$EXPECTED_OUT/decompile_dao_hack.hex.output" "$TEMPFILE2"
    assert_success
}
rm "$TEMPFILE1" "$TEMPFILE2"
