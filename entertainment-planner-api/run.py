#!/usr/bin/env python3
"""
Run the Entertainment Planner API server
"""
import uvicorn
from apps.api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
