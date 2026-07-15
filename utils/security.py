import bcrypt
from datetime import datetime, timedelta,timezone
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from cryptography.fernet import Fernet
import requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64

SECRET_KEY = "dcd17a590fcc5eff482bf100300300f0e4840d98fbb49e5e575ced13df3718fb"  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 31536000


security = HTTPBearer()



FERNET_KEY = b'17ZjpH8QHd6gYz3HHm13XQf776i81KOHk0Ba8BvT9uM=' 
fernet = Fernet(FERNET_KEY)

def create_access_token(data: dict, expires_delta: timedelta = None):
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + (expires_delta or timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS))
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt, int(expire.timestamp()), int(issued_at.timestamp())


def create_refresh_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    token = credentials.credentials
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE_KEY_PATH = os.path.join(BASE_DIR, "keys", "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(BASE_DIR, "keys", "public_key.pem")


try:
    with open(PRIVATE_KEY_PATH, "rb") as key_file:
        RSA_PRIVATE_KEY = serialization.load_pem_private_key(
            key_file.read(),
            password=None
        )
except Exception as e:
    print(f"Error loading private key: {e}")
    RSA_PRIVATE_KEY = None

def get_rsa_public_key() -> str:
    """Returns the RSA public key as a string for the frontend."""
    try:
        with open(PUBLIC_KEY_PATH, "r") as key_file:
            return key_file.read()
    except Exception as e:
        print(f"Error reading public key: {e}")
        return ""

def rsa_decrypt_password(encrypted_password_b64: str) -> str:
    if not RSA_PRIVATE_KEY:
        raise HTTPException(status_code=500, detail="RSA Private Key not loaded.")
    
    try:
        encrypted_bytes = base64.b64decode(encrypted_password_b64)
        
        try:
            decrypted = RSA_PRIVATE_KEY.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted.decode()
        except Exception:
            try:
                decrypted = RSA_PRIVATE_KEY.decrypt(
                    encrypted_bytes,
                    padding.PKCS1v15()
                )
                return decrypted.decode()
            except Exception:
                try:
                    decrypted = RSA_PRIVATE_KEY.decrypt(
                        encrypted_bytes,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA1()),
                            algorithm=hashes.SHA1(),
                            label=None
                        )
                    )
                    return decrypted.decode()
                except Exception as final_e:
                    raise final_e
                    
    except Exception as e:
        print(f"DEBUG: RSA Decryption failed for input: {encrypted_password_b64[:30]}...")
        print(f"DEBUG: Error details: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

def generate_salt() -> str:
    """Generates a new salt for bcrypt hashing."""
    return bcrypt.gensalt().decode('utf-8')

def hash_password_with_salt(password: str, salt: str) -> str:
    """Hashes a password with a specific salt."""
    return bcrypt.hashpw(password.encode('utf-8'), salt.encode('utf-8')).decode('utf-8')

def verify_password_with_salt(password: str, salt: str, hashed: str) -> bool:
    """Verifies a password against a hash using a specific salt."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    return fernet.decrypt(encrypted_password.encode()).decode()

def encrypt_card_no(card_no: str) -> str:
    return fernet.encrypt(card_no.encode()).decode()

def decrypt_card_no(encrypted_card_no: str) -> str:
    return fernet.decrypt(encrypted_card_no.encode()).decode()

def shorten_url_with_tinyurl(long_url: str) -> str:
    try:
        response = requests.get(f"https://tinyurl.com/api-create.php?url={long_url}")
        if response.status_code == 200:
            return response.text
        return long_url 
    except Exception:
        return long_url
    

