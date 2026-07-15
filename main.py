from fastapi import FastAPI
import os
from common.logger import log 
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from DB.db import SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from camera_devices import service as camera_service
from building import service as build_service
from menu.api import router as menu_router
from resident_device_assign.api import router as resident_device
from Users import service as user_service  
from Users.api import router as users_crud_router  
from Users.service import initialize_users_table, router as auth_router  
from block_building import service as block_building_service
from property.api import router as property_router
from block import service as block_service
from camera_management import service as camera_management_service
from assign_camera import service as assign_camera_service 
from resident_type import service as resident_type_service
from user_personal_details import service as user_personal_details_service
from resident_device_assign import service as resident_device_type_service
from visitor_qr_assign import service as visitor_qr_assign_service
from device_activities import service as device_activities_service
from a_visitor import service as adoc_visitor_service
from marketing_status import service as marketing_status_service
from marketing_type import service as marketing_type_service
from marketing.api import router as marketing_router
from marketing.apischedular import update_marketing_status
from apscheduler.schedulers.background import BackgroundScheduler
from property_common_area.api import router as property_common_area_service
from anpr_camera_assign.api import router as assign_camera_service_service
from camera.api import router as camera_type_service
from notificationss.api import router as notification_router_service
from banner_image.api import router as banner_image_service    
from DB.init import initialize_database
from anpr_device_activities import service as anpr_device_activities
from resident_call.service import router as resident_call_router
from poc_visitor import service as poc_visitor_service
from all_reports.api import router as all_reports_router
from Roles.api import router as roles_router
from Roles.service import initialize_roles_table
from vehicle_type import service as vehicle_type_service
from vehicle_configuration.api import router as vehicle_configuration_router
from invoice_master.api import router as invoice_master_router
from invoice_master.callback_router import router as payment_callback_router




app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/menu/images", StaticFiles(directory=os.path.join("menu", "images")), name="menu_images")
app.mount("/uploaded_faces", StaticFiles(directory="uploaded_faces"), name="uploaded_faces")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


app.mount("/banner_images", StaticFiles(directory="banner_images"), name="banner_images")


log("Server is Started")


scheduler = BackgroundScheduler()
scheduler.add_job(update_marketing_status, 'cron', hour=0, minute=0)
# scheduler.add_job(update_marketing_status, 'interval', minutes=5) 
scheduler.start()



@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.on_event("startup")
def on_startup():
    initialize_database()
    initialize_users_table()
    initialize_roles_table()
    update_marketing_status() 

# Include routers
app.include_router(camera_service.router)
app.include_router(users_crud_router)  
app.include_router(auth_router)  
app.include_router(roles_router)
app.include_router(build_service.router)
app.include_router(block_service.router)
app.include_router(block_building_service.router)
app.include_router(menu_router)
app.include_router(property_router)
app.include_router(camera_management_service.router)
app.include_router(assign_camera_service.router)
app.include_router(resident_device_type_service.router)
app.include_router(resident_type_service.router)
app.include_router(user_personal_details_service.router)
app.include_router(device_activities_service.router)
app.include_router(visitor_qr_assign_service.router)
app.include_router(adoc_visitor_service.router)
app.include_router(marketing_status_service.router)
app.include_router(marketing_type_service.router)
app.include_router(anpr_device_activities.router)
app.include_router(property_common_area_service)
app.include_router(marketing_router)
app.include_router(assign_camera_service_service)
app.include_router(camera_type_service, prefix="/camera", tags=["Camera"])
app.include_router(notification_router_service)
app.include_router(banner_image_service)
app.include_router(resident_call_router, prefix="/resident-call", tags=["Resident Call"])
app.include_router(resident_device)
app.include_router(poc_visitor_service.router)
app.include_router(all_reports_router)
app.include_router(vehicle_type_service.router)
app.include_router(vehicle_configuration_router)
app.include_router(invoice_master_router)
app.include_router(payment_callback_router)