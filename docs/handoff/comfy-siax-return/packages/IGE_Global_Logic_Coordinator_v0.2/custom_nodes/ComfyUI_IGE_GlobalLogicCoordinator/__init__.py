from pathlib import Path
import sys
_ROOT=Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0,str(_ROOT))
from .nodes import NODE_CLASS_MAPPINGS,NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY=None
__all__=["NODE_CLASS_MAPPINGS","NODE_DISPLAY_NAME_MAPPINGS"]
