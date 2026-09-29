"""Print live Python definition locations or one bounded source/map excerpt."""
import argparse
from pathlib import Path
import sys
from doc_inventory import excerpt, local, python_units


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--outline', help='project-relative Python source')
    mode.add_argument('--ref', help='path::qualified.symbol, path::<module>, or path#heading')
    parser.add_argument('--limit', type=int, default=65)
    args = parser.parse_args()
    try:
        if args.outline:
            for name, unit in python_units(local(args.root, args.outline).read_text(), args.outline).items():
                print(f'{args.outline}::{name}: {unit["spans"]}')
        else:
            result = excerpt(args.root, args.ref)
            print(f'{result["ref"]} sha256={result["sha256"]}')
            print('\n'.join(result['text'].splitlines()[:args.limit]))
    except (ValueError, OSError, SyntaxError) as exc:
        parser.exit(1, f'ESX orientation: {exc}\n')
