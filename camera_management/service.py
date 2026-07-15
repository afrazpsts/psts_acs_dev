from fastapi import APIRouter, Depends, HTTPException,Request
from fastapi.responses import JSONResponse
from requests.auth import HTTPDigestAuth
import requests
import urllib3
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils.security import decrypt_password
from utils.security import verify_token
from DB.db import get_db  
import xmltodict




urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# app = FastAPI()

router = APIRouter()

# @app.get("/hikvision/status")
# def check_camera_status(
#     ip: str = Query(..., description="IP address of the Hikvision camera"),
#     username: str = "admin",
#     password: str = "Psts@123"
# ):
#     url = f"https://{ip}/ISAPI/System/deviceInfo"

#     try:
#         response = requests.get(
#             url,
#             auth=HTTPDigestAuth(username, password),
#             timeout=5,
#             verify=False
#         )

#         if response.status_code == 200:
#             return {"status": "online", "ip": ip}
#         elif response.status_code == 401:
#             return {"status": "unauthorized", "ip": ip}
#         else:
#             return {"status": "offline", "ip": ip, "code": response.status_code}

#     except requests.exceptions.ConnectTimeout:
#         return {"status": "offline", "ip": ip, "reason": "timeout"}
#     except requests.exceptions.ConnectionError:
#         return {"status": "offline", "ip": ip, "reason": "connection error"}
#     except Exception as e:
#         return {"status": "offline", "ip": ip, "reason": str(e)}
    
# @router.get("/get_device_info", dependencies=[Depends(verify_token)])
# def get_device_info(ip: str, db: Session = Depends(get_db)):
#     try:
#         result = db.execute(text("SELECT * FROM camera_devices WHERE ip = :ip"), {"ip": ip})
#         row = result.fetchone()

#         if not row:
#             raise HTTPException(status_code=404, detail="Device with this IP not found.")

#         user_name = row[5]
#         password = decrypt_password(row[6])

#         url = f"https://{ip}/ISAPI/System/deviceInfo"

#         response = requests.get(
#             url,
#             auth=HTTPDigestAuth(user_name, password),
#             timeout=5,
#             verify=False
#         )

#         if response.status_code == 200:
#             return {
#                 "status": "success",
#                 "ip": ip,
#                 "device_info": response.text
#             }
#         elif response.status_code == 401:
#             return {
#                 "status": "unauthorized",
#                 "message": "Wrong username/password",
#                 "ip": ip
#             }
#         else:
#             return {
#                 "status": "error",
#                 "message": f"Unexpected status code: {response.status_code}",
#                 "ip": ip
#             }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/check_device_status", dependencies=[Depends(verify_token)])
def check_device_status(ip: str):
    test_urls = [
        f"https://{ip}/ISAPI/System/deviceInfo",
        f"http://{ip}/ISAPI/System/deviceInfo"
    ]

    for url in test_urls:
        try:
            response = requests.get(url, timeout=3, verify=False)

            if response.status_code in [200, 401]: 
                return {"ip": ip, "status": "online", "protocol": url.split(':')[0]}

            elif response.status_code in [403, 404, 405]:
                return {"ip": ip, "status": "online", "note": f"Responded with {response.status_code}", "protocol": url.split(':')[0]}

        except requests.exceptions.ConnectTimeout:
            continue
        except requests.exceptions.ConnectionError:
            continue
        except Exception as e:
            return {"ip": ip, "status": "error", "message": str(e)}

    return {"ip": ip, "status": "offline or unreachable"}

@router.get("/check_all_devices_status")
def check_all_devices_status(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT id, ip, name FROM camera_devices"))
        cameras = result.fetchall()

        if not cameras:
            raise HTTPException(status_code=404, detail="No cameras found.")

        status_list = []

        for cam in cameras:
            cam_id = cam[0]
            ip = cam[1]
            name = cam[2]

            test_urls = [
                f"https://{ip}/ISAPI/System/deviceInfo",
                f"http://{ip}/ISAPI/System/deviceInfo"
            ]

            status = {
                "id": cam_id,
                "name": name,
                "ip": ip,
                "status": "offline",
                "protocol": None
            }

            for url in test_urls:
                try:
                    response = requests.get(url, timeout=3, verify=False)

                    if response.status_code in [200, 401]:
                        status["status"] = "online"
                        status["protocol"] = url.split(":")[0]
                        break  

                except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
                    continue
                except Exception as e:
                    status["status"] = "error"
                    status["error"] = str(e)
                    break

            status_list.append(status)

        return status_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_device_info", dependencies=[Depends(verify_token)])
def get_device_info(ip: str, db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT * FROM camera_devices WHERE ip = :ip"), {"ip": ip})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Device with this IP not found.")

        user_name = row[5]
        password = decrypt_password(row[6])

        url = f"https://{ip}/ISAPI/System/deviceInfo"

        response = requests.get(
            url,
            auth=HTTPDigestAuth(user_name, password),
            timeout=5,
            verify=False
        )

        if response.status_code == 200:
            try:
                xml_data = response.text
                json_data = xmltodict.parse(xml_data)
                return {
                    "status": "success",
                    "ip": ip,
                    "device_info": json_data
                }
            except Exception:
                return {
                    "status": "success",
                    "ip": ip,
                    "device_info": response.text  
                }

        elif response.status_code == 401:
            return {
                "status": "unauthorized",
                "message": "Wrong username/password",
                "ip": ip
            }
        else:
            return {
                "status": "error",
                "message": f"Unexpected status code: {response.status_code}",
                "ip": ip
            }

    except requests.exceptions.ConnectTimeout:
        return {"status": "offline", "message": "Timeout while connecting", "ip": ip}
    except requests.exceptions.ConnectionError:
        return {"status": "offline", "message": "Connection error", "ip": ip}
    except Exception as e:
        return {"status": "error", "message": str(e), "ip": ip}




