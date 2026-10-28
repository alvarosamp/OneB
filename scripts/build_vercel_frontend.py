"""Put Vite's static output in the CDN directory used by Vercel FastAPI."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
shutil.copytree(root / "frontend" / "dist", root / "public", dirs_exist_ok=True)
