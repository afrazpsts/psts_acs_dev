from DB.db import engine, Base

def initialize_database():
    """
    Ensure all model files are imported before creating tables.
    This prevents missing tables in PyInstaller builds.
    """

    from building.building import PropertyBuilding
    from company.company import Company
    from menu.menu import MenuList
    from camera_devices.camera_devices import Device
    from property.property import Property
    from area_type.area_type import AreaType
    from building_level.building_level import BuildingLevel
    from building_unit.building_unit import BuildingUnit
    from block.block import Block
    from block_building.block_building import BlockBuilding
    from assign_camera.assign_camera import AssignCamera
    from resident_type.resident_type import ResidentList
    from user_personal_details.user_personal_details import UserPersonalDetails
    from user_emergancy.user_emergancy import UserEmergencyContact
    from user_access_details.user_access_details import UserAccessDetail
    from resident_device_assign.resident_device import ResidentDeviceAssign
    from visitor_qr_assign.visitor_qr_assign import VisitorQrAssign
    from a_visitor.adoc_visitor import AdocVisitor
    from device_activities.device_activities import DeviceActivities
    from resident_device_assign.resident_device import ResidentDeviceAssign 
    from marketing_status.marketing_status import MarketingStatus
    from marketing_type.marketing_type import MarketingType
    from marketing.marketing import Marketing
    from property_common_area.property_common_area import PropertyCommonArea
    from anpr_camera_assign.anpr_camera_assign import LicensePlateAccess
    from camera.camera import Camera
    from device_employee_number.device_employee_number import UserEmployee
    from banner_image.banner_image import BannerImage
    from anpr_device_activities.anpr_device_activities import AnprDeviceActivities
    from resident_call.resident_call import Call
    from Users.users import Users
    from Roles.roles import Roles
    from user_menu_permissions.user_menu_permissions import UserMenuPermission
    from activity_logs.activity_logs import ActivityLogs
    from media_manager.media_manager import MediaManager
    from resident_family_members.resident_family_members import ResidentFamilyMembers
    from vehicle_type.vehicle_type import VehicleType
    from vehicle_configuration.vehicle_configuration import VehicleConfiguration
    from invoice_master.invoice_master import InvoiceMaster
    from invoice_vehicle_items.invoice_vehicle_items import InvoiceVehicleItems
    from recurring_invoice_settings.recurring_invoice_settings import RecurringInvoiceSettings
    from invoice_payments.invoice_payments import InvoicePayments
    from invoice_recurring_residents.invoice_recurring_residents import InvoiceRecurringResidents

    print("Tables detected before create_all():", list(Base.metadata.tables.keys()))

    Base.metadata.create_all(bind=engine)
    print(" Database tables created successfully.")
