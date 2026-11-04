#!/usr/bin/env python3
"""Copies a grit .pak file, leaving out resources Electron never uses.

Some upstream .grd files bundle large resources for Chrome-only UI alongside
resources that Electron does need, so the whole .pak has to be shipped. This
drops the named resources from such a .pak before it is merged into
resources.pak.

Resources are selected by name (fnmatch patterns such as IDR_FOO_*) and mapped
to ids with the grit-generated header of the same .grd, so the patterns stay
valid when resource ids are renumbered.

Removing a resource that the binary can still request would be a bug; on
builds with resource allowlisting, //electron:electron_resource_allowlist_check
fails the build if that happens.
"""

import argparse
import fnmatch
import re
import sys

# grit emits either `#define NAME 123` or, with allowlist support,
# `#define NAME (::ui::AllowlistedResource<123>(), 123)`.
_DEFINE_RE = re.compile(
    r'^#define (\w+) (?:\(::ui::AllowlistedResource<(\d+)>|(\d+)\b)',
    re.MULTILINE)


def resource_ids_by_name(header):
  with open(header, encoding='utf-8') as f:
    text = f.read()
  return {
      m.group(1): int(m.group(2) or m.group(3))
      for m in _DEFINE_RE.finditer(text)
  }


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--input', required=True, help='Source .pak file')
  parser.add_argument('--output', required=True, help='Stripped .pak file')
  parser.add_argument('--header', required=True,
                      help='grit header generated from the same .grd')
  parser.add_argument('--grit-dir', required=True,
                      help='Path to //tools/grit for the data_pack module')
  parser.add_argument('--exclude', action='append', required=True,
                      help='fnmatch pattern of resource names to drop '
                      '(repeatable)')
  args = parser.parse_args()

  sys.path.insert(0, args.grit_dir)
  from grit.format import data_pack

  ids = resource_ids_by_name(args.header)
  excluded = set()
  for pattern in args.exclude:
    matches = {i for name, i in ids.items() if fnmatch.fnmatch(name, pattern)}
    if not matches:
      # Upstream renamed or removed the resources; drop the stale pattern.
      print(f'error: --exclude {pattern} matches nothing in {args.header}',
            file=sys.stderr)
      return 1
    excluded |= matches

  pack = data_pack.ReadDataPack(args.input)
  resources = {
      rid: data
      for rid, data in pack.resources.items() if rid not in excluded
  }
  data_pack.WriteDataPack(resources, args.output, pack.encoding)
  return 0


if __name__ == '__main__':
  sys.exit(main())
