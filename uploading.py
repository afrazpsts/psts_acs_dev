import requests
import urllib3
import json
import os

camera_ip = "192.168.1.8"
image_path = "face.jpg"
token = "LRnEEWoJvMGrDMG16Sk7mAYLw5TTaDaQ"  # Replace with your real token

metadata = {
    "faceLibType": "blackFD",
    "FDID": "1",
    "FPID": "44"
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = f"https://{camera_ip}/ISAPI/Intelligent/FDLib/FDSetUp"
print(f"\n📡 Target URL: {url}")

if not os.path.exists(image_path):
    print(f"❌ Image not found at path: {image_path}")
    exit(1)

with open(image_path, "rb") as img_file:
    image_data = img_file.read()
    print(f"\n➡️ Sending metadata:\n {json.dumps(metadata, indent=2)}")
    print(f"➡️ Sending image size: {len(image_data)} bytes")

    img_file.seek(0)

    files = {
        "format": (None, "json"),
        "token": (None, token),
        "FaceDataRecord": ("FaceDataRecord", json.dumps(metadata), "application/json"),
        "img": ("face.jpg", img_file, "image/jpeg")
    }

    try:
        response = requests.put(
            url,
            files=files,
            timeout=10,
            verify=False  # Skip SSL verification
        )
    except Exception as e:
        print(f"❌ Request failed: {e}")
        exit(1)

print(f"\n✅ Status Code: {response.status_code}")
print(f"🔗 URL: {response.url}")
print("📦 Response Body:\n", response.text)
