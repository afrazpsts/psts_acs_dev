from pydantic import BaseModel
from typing import Optional,List

class MenuCreate(BaseModel):
    name: str
    key: str
    description: Optional[str] = None
    navigation: Optional[str] = None
    menu_for: int
    is_submenu: Optional[int] = 0
    parent_menu_id: Optional[int] = None
    allowed_user_role: Optional[str] = None
    allowed_department: Optional[str] = None
    service_id: Optional[int] = None
    access_ids: Optional[str] = None
    sort_order: Optional[int] = None

class RoleMenuPermissionRequest(BaseModel):
    role_id: int
    menu_ids: List[int]
    enabled: int

class MenuOut(MenuCreate):
    id: int
    icon_path: Optional[str]
    active_path:Optional[str]

