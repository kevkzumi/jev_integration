"""Command line interface: python3 -m calc.cli OP A B"""
import argparse
import sys

from . import core

OPS = {"add": core.add, "sub": core.subtract, "mul": core.multiply, "div": core.divide}


def build_parser():
    p = argparse.ArgumentParser(prog="calc", description="tiny calculator")
    p.add_argument("op", choices=sorted(OPS))
    p.add_argument("a", type=float)
    p.add_argument("b", type=float)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = OPS[args.op](args.a, args.b)
    except ZeroDivisionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
