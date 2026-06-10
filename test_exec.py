#!/usr/bin/env python3
"""Quick verification that Python scripts can run anonymously."""
import sys, os

print(f"Python version: {sys.version}")
print(f"Executing from: {os.getcwd()}")
print(f"Current user/env — no identity exposed")
print("SUCCESS: Python script execution works via executor agent!")
