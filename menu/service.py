import os
import shutil
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import UploadFile,HTTPException
from datetime import datetime
import json
from typing import List



UPLOAD_FOLDER = "menu/images/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DEFAULT_BANNER_IMAGE = os.path.join(UPLOAD_FOLDER, "default_banner.jpg")


def parse_optional_int(value: str):
    return int(value) if value and value.strip() else None

async def create_menu(
    name: str,
    key: str,
    description: str,
    navigation: str,
    menu_for: int,
    is_submenu: int,
    parent_menu_id: str,
    allowed_user_role: str,
    allowed_department: str,
    service_id: str,
    access_ids: str,
    sort_order: str,
    icon: UploadFile,
    db: Session
):
    icon_path = None
    if icon:
        filename = f"{datetime.utcnow().timestamp()}_{icon.filename}"
        file_location = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(icon.file, buffer)
        icon_path = file_location

    db.execute(text("""
        INSERT INTO menu_list (
            name, `key`, description, navigation, icon_path, active_path,
            menu_for, is_submenu, parent_menu_id,
            allowed_user_role, allowed_department,
            service_id, access_ids, sort_order
        ) VALUES (
            :name, :key, :description, :navigation, :icon_path, :active_path,
            :menu_for, :is_submenu, :parent_menu_id,
            :allowed_user_role, :allowed_department,
            :service_id, :access_ids, :sort_order
        )
    """), {
        "name": name,
        "key": key,
        "description": description,
        "navigation": navigation,
        "icon_path": icon_path,
        "active_path": icon_path,
        "menu_for": menu_for,
        "is_submenu": is_submenu,
        "parent_menu_id": parse_optional_int(parent_menu_id),
        "allowed_user_role": allowed_user_role,
        "allowed_department": allowed_department,
        "service_id": parse_optional_int(service_id),
        "access_ids": access_ids,
        "sort_order": parse_optional_int(sort_order)
    })

    db.commit()

    return {
        "status": 200,
        "message": "Menu created successfully."
    }


def get_menu_list(db: Session, user_role: int):
    try:
        result = db.execute(text("SELECT * FROM menu_list ORDER BY id ASC"))
        rows = result.fetchall()
        all_menus = [dict(row._mapping) for row in rows]

        permissions_result = db.execute(text("""
            SELECT menu_id, enabled 
            FROM role_menu_permission 
            WHERE role_id = :role_id
        """), {"role_id": user_role})
        
        permissions = {row[0]: row[1] for row in permissions_result.fetchall()}
        
        print(f"Permissions for role {user_role}: {permissions}")
        
        menu_by_id = {menu['id']: menu for menu in all_menus}
        
        for menu in all_menus:
            menu['sub_menu'] = []

        menu_tree = []

        def parse_roles(value):
            """Parse allowed_user_role field into a list of ints."""
            if value is None or value == "":
                return []

            if isinstance(value, list):
                return [int(x) for x in value if str(x).isdigit()]

            if isinstance(value, int):
                return [value]

            if isinstance(value, str):
                value = value.strip()
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [int(x) for x in parsed if str(x).isdigit()]
                    elif isinstance(parsed, int):
                        return [parsed]
                except json.JSONDecodeError:
                    if value.isdigit():
                        return [int(value)]
                    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]

            return []

        def is_menu_allowed(menu_id, allowed_roles):
            """Check if menu is allowed based on role_menu_permission first, then allowed_user_role"""
            if menu_id in permissions:
                is_allowed = permissions[menu_id] == 1
                print(f"Menu {menu_id} has explicit permission: {is_allowed} (enabled={permissions[menu_id]})")
                return is_allowed
            
            is_allowed = user_role in allowed_roles
            print(f"Menu {menu_id} using default permission: {is_allowed}")
            return is_allowed

        allowed_menu_ids = set()
        for menu in all_menus:
            allowed_roles = parse_roles(menu.get("allowed_user_role"))
            if is_menu_allowed(menu["id"], allowed_roles):
                allowed_menu_ids.add(menu["id"])

        print(f"Allowed menu IDs: {allowed_menu_ids}")

        for menu in all_menus:
            if menu["id"] not in allowed_menu_ids:
                continue

            parent_id = menu.get("parent_menu_id")
            if parent_id and parent_id in allowed_menu_ids:
                if parent_id in menu_by_id:
                    menu_by_id[parent_id]['sub_menu'].append(menu)
            elif not parent_id:
                menu_tree.append(menu)

        print(f"Menu tree has {len(menu_tree)} top-level items")
        for menu in menu_tree:
            print(f"Top menu: {menu['name']} (ID: {menu['id']}) with {len(menu['sub_menu'])} submenus")
            for sub in menu['sub_menu']:
                print(f"  Submenu: {sub['name']} (ID: {sub['id']})")

        return {
            "status": 200,
            "success": True,
            "message": "Data retrieved successfully.",
            "data": {
                "menu": menu_tree
            }
        }

    except Exception as e:
        print(f"Error in get_menu_list: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Menu fetch failed: {str(e)}")
    
def set_role_menu_permission(role_id: int, menu_ids: List[int], enabled: int, db):
    try:
        result = db.execute(text("SELECT id, parent_menu_id, allowed_user_role FROM menu_list"))
        all_menus = [dict(row._mapping) for row in result.fetchall()]
        
        parent_to_children = {}
        menu_lookup = {menu['id']: menu for menu in all_menus}
        
        for menu in all_menus:
            parent_id = menu.get('parent_menu_id')
            if parent_id:
                if parent_id not in parent_to_children:
                    parent_to_children[parent_id] = []
                parent_to_children[parent_id].append(menu['id'])
        
        current_permissions = db.execute(text("""
            SELECT menu_id, enabled 
            FROM role_menu_permission 
            WHERE role_id = :role_id
        """), {"role_id": role_id}).fetchall()
        
        current_permission_map = {row[0]: row[1] for row in current_permissions}
        
        print(f"Current permissions for role {role_id}: {current_permission_map}")
        
        def parse_roles(value):
            """Parse allowed_user_role field into a list of ints."""
            if value is None or value == "":
                return []

            if isinstance(value, list):
                return [int(x) for x in value if str(x).isdigit()]

            if isinstance(value, int):
                return [value]

            if isinstance(value, str):
                value = value.strip()
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [int(x) for x in parsed if str(x).isdigit()]
                    elif isinstance(parsed, int):
                        return [parsed]
                except json.JSONDecodeError:
                    if value.isdigit():
                        return [int(value)]
                    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]

            return []
        
        def is_enabled_by_default(menu_id):
            if menu_id in menu_lookup:
                allowed_roles = parse_roles(menu_lookup[menu_id].get('allowed_user_role'))
                return role_id in allowed_roles
            return False
        
        def get_all_child_ids(menu_id):
            child_ids = []
            if menu_id in parent_to_children:
                for child_id in parent_to_children[menu_id]:
                    child_ids.append(child_id)
                    child_ids.extend(get_all_child_ids(child_id))
            return child_ids
        
        def get_parent_id(menu_id):
            if menu_id in menu_lookup:
                return menu_lookup[menu_id].get('parent_menu_id')
            return None
        
        def has_enabled_children(menu_id, exclude_ids=None):
            if exclude_ids is None:
                exclude_ids = set()
            
            if menu_id in parent_to_children:
                for child_id in parent_to_children[menu_id]:
                    if child_id in exclude_ids:
                        continue
                    
                    if child_id in current_permission_map:
                        child_enabled = current_permission_map[child_id] == 1
                        print(f"  Checking child {child_id}: explicit permission enabled={child_enabled}")
                    else:
                        child_enabled = is_enabled_by_default(child_id)
                        print(f"  Checking child {child_id}: default permission enabled={child_enabled}")
                    
                    if child_enabled:
                        return True
                    
                    if has_enabled_children(child_id, exclude_ids):
                        return True
            return False
        
        all_menu_ids_to_update = set(menu_ids)
        
        for menu_id in menu_ids:
            print(f"\nProcessing menu_id: {menu_id}, enabled={enabled}")
            
            if enabled == 1:  
                child_ids = get_all_child_ids(menu_id)
                all_menu_ids_to_update.update(child_ids)
                print(f"  Adding children: {child_ids}")
                
                parent_id = get_parent_id(menu_id)
                while parent_id:
                    all_menu_ids_to_update.add(parent_id)
                    print(f"  Adding parent: {parent_id}")
                    parent_id = get_parent_id(parent_id)
            
            else:  
                child_ids = get_all_child_ids(menu_id)
                all_menu_ids_to_update.update(child_ids)
                print(f"  Adding children to disable: {child_ids}")
                
                parent_id = get_parent_id(menu_id)
                print(f"  Checking parent {parent_id} for other enabled children")
                
                while parent_id:
                    disabling_ids = all_menu_ids_to_update.copy()
                    
                    has_other_enabled = has_enabled_children(parent_id, disabling_ids)
                    
                    print(f"  Parent {parent_id} has other enabled children: {has_other_enabled}")
                    
                    if not has_other_enabled:
                        print(f"  Adding parent {parent_id} to disable list (no other enabled children)")
                        all_menu_ids_to_update.add(parent_id)
                        
                        parent_id = get_parent_id(parent_id)
                    else:
                        break
        
        print(f"\nFinal all_menu_ids_to_update: {all_menu_ids_to_update}")
        
        for menu_id in all_menu_ids_to_update:
            check = db.execute(text("""
                SELECT id FROM role_menu_permission
                WHERE role_id = :role_id AND menu_id = :menu_id
            """), {"role_id": role_id, "menu_id": menu_id}).fetchone()

            if check:
                db.execute(text("""
                    UPDATE role_menu_permission
                    SET enabled = :enabled, updated_at = NOW()
                    WHERE role_id = :role_id AND menu_id = :menu_id
                """), {
                    "role_id": role_id,
                    "menu_id": menu_id,
                    "enabled": enabled
                })
                print(f"  Updated menu_id {menu_id} to enabled={enabled}")
            else:
                db.execute(text("""
                    INSERT INTO role_menu_permission (role_id, menu_id, enabled, created_at, updated_at)
                    VALUES (:role_id, :menu_id, :enabled, NOW(), NOW())
                """), {
                    "role_id": role_id,
                    "menu_id": menu_id,
                    "enabled": enabled
                })
                print(f"  Inserted menu_id {menu_id} with enabled={enabled}")

        db.commit()

        return {
            "status": 200,
            "message": f"Menu permissions updated successfully for {len(all_menu_ids_to_update)} menu(s) (cascade applied)"
        }

    except Exception as e:
        db.rollback()
        print(f"Error in set_role_menu_permission: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))