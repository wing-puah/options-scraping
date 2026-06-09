import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))              # lib.*
sys.path.insert(0, str(_ROOT / "scripts"))  # scrape, collect, fetch, etc.
