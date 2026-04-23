"""
Tenant Context Loader
Loads tenant-specific accounting rules and vendor mappings for injection
into agent prompts. Add a new tenant by creating a matching module in this
directory and registering it in TENANT_CONTEXT_MAP below.
"""

from typing import Optional


def load_tenant_context(tenant_id: str) -> Optional[str]:
    """
    Returns the tenant-specific context string for a given tenant_id,
    or None if no context is defined for that tenant.
    """
    TENANT_CONTEXT_MAP = {
        "mersi_us": _load_mersi,
    }

    loader_fn = TENANT_CONTEXT_MAP.get(tenant_id.lower())
    if loader_fn:
        return loader_fn()
    return None


def _load_mersi() -> str:
    from config.tenant_contexts.mersi_us import get_context
    return get_context()
