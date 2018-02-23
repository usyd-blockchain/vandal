#!/usr/bin/env bats

load test_helper

# REPOROOT

# module (use as prefix in @test messages)
M="decompile (regression tests):"

# module path
MP="bin/decompile"

# test decompilation of each *.hex example
@test "$M testing sensible default configuration (long_running.hex finish < 20s)" {
    run timeout 20 $MP $REGRESSION/long_running.hex
    assert_success
}
