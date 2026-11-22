"""Public interface of the identity module. Other modules may import ONLY this file.

Usage in another module's router:
    from app.modules.identity.public import CurrentUser, Permission, require_permission

    @router.post("/apply")
    def apply(user: CurrentUser = Depends(require_permission(Permission.SCENARIO_APPLY))): ...
"""
from app.modules.identity.application.contracts import CurrentUser
from app.modules.identity.application.dependencies import get_current_user, require_permission
from app.modules.identity.domain.permissions import ROLE_PERMISSIONS, Permission

__all__ = ["CurrentUser", "Permission", "ROLE_PERMISSIONS", "get_current_user", "require_permission"]
