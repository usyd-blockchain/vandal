# `test/hex/`

Hex test cases used for testing the function extraction module (currently)

*basic_example.hex* - a simple contract that does some basic arithmetic, with two public functions and one private function.

*example_two.hex* - same as basic_example, but with two parameters for the private function.

*mutual_recursion.hex* - a contract with two public functions calling two mutually recursive functions (together they compute a factorial, with one handling even and the other odd numbers).

*recursion.hex* - a contract with two public functions calling a recursive function which computes a factorial.
