import sys
from pathlib import Path

# Add project root to Python path so 'src' is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )