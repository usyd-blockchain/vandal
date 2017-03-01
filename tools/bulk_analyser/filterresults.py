#!/usr/bin/env python3
"""filter_results.py: filter down the results from analyse.py""" 

import argparse
import json

JSON_FILE = "results.json"

parser = argparse.ArgumentParser()
parser.add_argument("-i",
                    "--in_file",
                    nargs="?",
                    default=JSON_FILE,
                    const=JSON_FILE,
                    metavar="FILEPATH",
                    help="take input from the specified file."
                    )

parser.add_argument("-n",
                    "--names_only",
                    default=False,
                    action="store_true",
                    help="output filenames only."
                   )

parser.add_argument("-p",
                    "--properties",
                    nargs="*",
                    default=[],
                    metavar="NAME",
                    help="include results exhibiting all of the given properties."
                   )

parser.add_argument("-P",
                    "--exclude_properties",
                    nargs="*",
                    default=[],
                    metavar="NAME",
                    help="exclude results exhibiting any of the given properties."
                   )

parser.add_argument("-f",
                    "--flags",
                    nargs="*",
                    default=[],
                    metavar="NAME",
                    help="include results exhibiting all of the given flags."
                   )

parser.add_argument("-F",
                    "--exclude_flags",
                    nargs="*",
                    default=[],
                    metavar="NAME",
                    help="exclude results exhibiting any of the given flags."
                   )

args = parser.parse_args()


def satisfies(triple):
  """
  Args:
    triple: a triple of [filename, properties, flags]

  Returns:
    True iff the conditions specified in the args are satisfied.
  """
  filename, properties, flags = triple

  result = True

  for p in args.properties:
    if p not in properties:
      result = False
      break
  if result:
    for f in args.flags:
      if f not in flags:
        result = False
        break
  if result:
    for p in args.exclude_properties:
      if p in properties:
        result = False
        break
  if result:
    for f in args.exclude_flags:
      if f in flags:
        result = False
        break
  
  return result

  
with open(args.in_file, 'r') as f:
  results = json.loads(f.read())
  with open("filtered_results.json", 'w') as g:
    filtered = filter(satisfies, results)
    if args.names_only:
      filtered = map(lambda t: t[0], filtered)
    filtered = list(filtered)
    print("{} results filtered down to {}.".format(len(results), len(filtered)))
    g.write(json.dumps(filtered))
