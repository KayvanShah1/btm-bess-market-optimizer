"""Command-line entry point for the eSett quarterly historical downloader.

Run with: uv run --package bess-optimizer python scripts/esett_open_data.py --help
The reusable API implementation is in bess_optimizer.data.esett_api.
"""
from bess_optimizer.data.esett_api import main

if __name__ == "__main__":
    main()
