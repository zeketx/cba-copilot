import os
import sys
from pathlib import Path

os.environ["PYDANTIC_AI_NO_BANNER"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
