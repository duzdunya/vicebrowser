#!/usr/bin/env python3
"""
Build script for vicebrowser using PyInstaller
"""
import subprocess
import sys
import os

def build_executable():
    """Build the PyInstaller executable"""
    print("Building vicebrowser executable...")
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "vicebrowser.spec"
    ]
    
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    
    if result.returncode == 0:
        print("\n✓ Build successful!")
        print("Executable location: dist/vicebrowser/vicebrowser")
    else:
        print("\n✗ Build failed!")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()
