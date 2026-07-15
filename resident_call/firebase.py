import firebase_admin
from firebase_admin import credentials, messaging
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", os.path.join(BASE_DIR, "..", "notificationss", "accountkey.json"))
cred_path = os.path.abspath(cred_path)  

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Warning: Could not initialize Firebase in resident_call. Error: {e}")

def sending_notifications(tokens: list, title: str, body: str, data: dict = None):
    success_count = 0
    failure_count = 0

    for token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
                data=data or {}
            )
            print(f"Sending FCM message:\nTitle: {title}\nBody: {body}\nToken: {token}\nData: {data}")
            response = messaging.send(message)
            print(f"Successfully sent message to token: {token} | response: {response}")
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to token: {token} | error: {str(e)}")
            failure_count += 1

    return {"success_count": success_count, "failure_count": failure_count}
