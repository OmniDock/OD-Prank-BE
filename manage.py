#!/usr/bin/env python3
"""
Django-style management script for running commands
Usage: python manage.py <command>
"""
import sys
import importlib
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command>")
        print("Available commands:")
        commands_dir = Path("management/commands")
        if commands_dir.exists():
            for file in commands_dir.glob("*.py"):
                if file.name != "__init__.py":
                    print(f"  {file.stem}")
        return
    
    command = sys.argv[1]
    
    try:
        module = importlib.import_module(f"management.commands.{command}")
        if hasattr(module, 'run'):
            module.run()
        else:
            print(f"Command '{command}' does not have a run() function")
    except ImportError:
        print(f"Command '{command}' not found")
        return

if __name__ == "__main__":
    main()