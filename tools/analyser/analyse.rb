#!/usr/bin/env ruby

require 'tmpdir'

SCRIPT_DIR = File.expand_path(File.dirname(__FILE__))

# String constants
VANDAL = "timeout %s #{File.join(SCRIPT_DIR, "../../bin/decompile")} %s"
VANDAL_ARGS = "-o CALL JUMPI SSTORE SLOAD MLOAD MSTORE -d -n -t %s %s"
SOUFFLE = "timeout %s /opt/souffle/bin/souffle %s"
SOUFFLE_ARGS = "-F %s -D %s %s"

# Timeout for running vandal
VANDAL_TIMEOUT = 20
SOUFFLE_TIMEOUT = 120

# Check correct command-line args
if ARGV.length != 2
    abort "Usage: analyse.rb SPEC_FILE BYTECODE_FILE"
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
    souffle = SOUFFLE % [SOUFFLE_TIMEOUT, args]
    return `#{souffle}`
end

def check_exit(progname, stdout, code, timeout)
    status = $?.exitstatus
    basename = File.basename(code)
    prog = progname.upcase
    if status == 124
        puts "#{basename},TIMEOUT_#{prog}_#{timeout}"
        raise
    elsif status != 0
        puts "#{basename},ERROR_#{prog}"
        STDERR.puts "#{basename} Error running #{prog}"
        STDERR.puts "#{stdout}"
        raise
    end
end

# create and use a temp directory
dir = Dir.mktmpdir
begin
    outdir = File.join(dir, "/out")
    Dir.mkdir outdir

    stdout = run_vandal(dir, code)
    check_exit('Vandal', stdout, code, VANDAL_TIMEOUT)

    stdout = run_souffle(dir, outdir, spec)
    check_exit('Souffle', stdout, code, SOUFFLE_TIMEOUT)

    vulns = []
    Dir.glob(File.join(outdir, "/*.csv")).each do |f|
        if File.size(f) > 0
            vulns.push(File.basename(f).split('.')[0])
        end
    end
    vulns.sort!
    puts "#{File.basename(code)},#{vulns.join(',')}"
rescue
    # do nothing
    # TODO: improve this with proper exceptions
ensure
    # remove the temp directory
    FileUtils.remove_entry dir
end
