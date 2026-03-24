#!/usr/bin/env python3
"""
Simple script to run Folio from source
"""

import os
import sys

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

if __name__ == "__main__":
    from main import main
    sys.exit(main())