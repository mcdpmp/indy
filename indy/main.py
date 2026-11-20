"""Entry point: python -m indy.main serve"""

import sys

import uvicorn

from .config import load_config
from .server import create_app

PORT = 5112


def main(argv: list[str]) -> int:
    if argv[:1] != ["serve"]:
        print("usage: python -m indy.main serve")
        return 2
    uvicorn.run(create_app(load_config()), host="0.0.0.0", port=PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
