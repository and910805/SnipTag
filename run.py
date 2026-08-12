"""給 PyInstaller 打包用的進入點（平常用 `python -m sniptag` 即可）。"""
import sys

from sniptag.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
