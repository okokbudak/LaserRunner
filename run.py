import sys
import os

# Host paket yolunu ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "host"))

from laserrunner.main import main

if __name__ == "__main__":
    main()
