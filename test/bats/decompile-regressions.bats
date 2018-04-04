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

@test "$M testing function extraction where private function body is not found (bug 48) (private_func_no_body.hex)" {
    run $MP $REGRESSION/private_func_no_body.hex
    assert_success
}
