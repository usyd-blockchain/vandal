#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="disassemble:"

# module path
MP="bin/disassemble"

@test "$M check --help success" {
    $MP --help
}

# test disassembly of each *.hex example
@test "$M disassembles examples/*.hex successfully without flags" {
    for eg in examples/*.hex
    do
        $MP $eg
        assert_success
    done
}

# test prettified output
@test "$M disassembles examples/*.hex successfully with -p/--prettify flag" {
    for eg in examples/*.hex
    do
        $MP -p $eg
        assert_success
        $MP --prettify $eg
        assert_success
    done
}

# test failed disassembly in strict mode
@test "$M fails when disassembling examples/invalid_*.hex with -s/--strict flag" {
    for eg in examples/invalid_*.hex
    do
        run $MP -s $eg
        assert_failure
        run $MP --strict $eg
        assert_failure
    done
}
