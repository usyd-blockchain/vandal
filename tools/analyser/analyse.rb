#!/usr/bin/env ruby

require 'tmpdir'

# String constants
VANDAL = "timeout %s ../../bin/decompile %s"
VANDAL_ARGS = "-o CALL JUMPI SSTORE SLOAD MLOAD MSTORE -d -n -t %s %s"
SOUFFLE = "/opt/souffle/bin/souffle %s"
SOUFFLE_ARGS = "-F %s -D %s %s"

# Timeout for running vandal
VANDAL_TIMEOUT = 20

# Check correct command-line args
if ARGV.length != 2
    abort("Usage: analyse.rb SPEC_FILE BYTECODE_FILE")
end

# Read spec and contract filename
spec = ARGV[0]
code = ARGV[1]

def run_vandal(fact_dir, bytecode_filepath)
    args = VANDAL_ARGS % [fact_dir, bytecode_filepath]
    vandal = VANDAL % [VANDAL_TIMEOUT, args]
    return `#{vandal}`
end

def run_souffle(fact_dir, out_dir, spec_filepath)
    args = SOUFFLE_ARGS % [fact_dir, out_dir, spec_filepath]
    souffle = SOUFFLE % [args]
    return `#{souffle}`
end

def check_exit(progname, stdout, code)
    status = $?.exitstatus
    if status == 124
        abort "#{File.basename(code)},VANDAL_TIMEOUT_#{VANDAL_TIMEOUT}"
    elsif status != 0
        puts "non-zero exit status when running #{progname}!"
        puts stdout
        abort()
    end
end

# create and use a temp directory
dir = Dir.mktmpdir
begin
    outdir = "#{dir}/out"
    Dir.mkdir outdir

    stdout = run_vandal(dir, code)
    check_exit('Vandal', stdout, code)

    stdout = run_souffle(dir, outdir, spec)
    check_exit('Souffle', stdout, code)

    vulns = []
    Dir.glob("#{outdir}/*.csv").each do |f|
        if File.size(f) > 0
            vulns.push(File.basename(f).split('.')[0])
        end
    end
    vulns.sort!
    puts "#{File.basename(code)},#{vulns.join(',')}"
ensure
    # remove the temp directory
    FileUtils.remove_entry dir
end
