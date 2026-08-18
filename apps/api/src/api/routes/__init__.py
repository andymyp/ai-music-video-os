"""HTTP routes (MASTER §29; MAD-001 §45).

Phase 19 adds the production API; asset/config/provider routes from MAD-001 §45
arrive in later phases. The public router is assembled from the production
endpoints so ``create_app`` mounts a single object.
"""
from __future__ import annotations

from api.routes.productions import router as productions_router

__all__ = ["productions_router"]
