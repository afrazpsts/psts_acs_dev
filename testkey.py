import base64
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

password = "admin123"

PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzi02OE4gM2LtKftNmqvX
/c2KzL28GtFu2YyUKaAcZd6WMty9Liav+fiWHCC8ZFJMTWH0ZN+jUSZwea4XLTeU
lIVqG0xwGVgJL6FIGqOE4BIJSrRU2CbqT1MyOAyXyY5hTmS3ia7chh9KQdvASdlX
hhR0KihX8m41TdkPKUACM/cIhbPJXIYVqUi8rPJ6lI7XvsO6GFsTjXPFW6R4MgkA
TlX1sBUvf9+WLv24cXzGRiWh/QGKBXnvrtssur0jDueFv2PXe2AnY57kRZFk4cbp
sKNlsmvC3gZyHGH14KVwCA0MBSmKn5StxymXem/yofDG7x6elLk34+yyV4chusl/
PwIDAQAB
-----END PUBLIC KEY-----

"""
public_key = serialization.load_pem_public_key(
    PUBLIC_KEY.encode()
)

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PUBLIC_KEY_PATH = os.path.join(BASE_DIR, "keys", "public_key.pem")

# with open(PUBLIC_KEY_PATH, "rb") as f:
#     public_key = serialization.load_pem_public_key(f.read())

encrypted = public_key.encrypt(
    password.encode(),
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)

encrypted_b64 = base64.b64encode(encrypted).decode()

print("Encrypted Password Base64:")
print(encrypted_b64)
