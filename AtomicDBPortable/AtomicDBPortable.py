#!/usr/bin/env python3
"""
AtomicDB Portable - Top-Level Application Entry Point
Can be compiled directly with PyInstaller or executed with Python 3.10+
"""

import os
import sys

# Ensure 'src' and root directory are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.main import main

if __name__ == "__main__":
    main()
