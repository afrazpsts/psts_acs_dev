import os
from dotenv import load_dotenv

load_dotenv()

class HitPayConfig:
    """HitPay Payment Configuration"""
    
    SANDBOX_API_KEY = "test_b59f721f71ebae861c52dabb20fcd150aef5bb8887f5ca2bc791a50f8187c098"
    SANDBOX_SALT = "KyJmYweE1kNQUqMivIEo7ouwmHViFnhm1LdXRAUZUEiDB8bdkRErK2V5PZipYFvO"
    SANDBOX_API_URL = "https://api.sandbox.hit-pay.com/v1"
    
    PRODUCTION_API_KEY = os.getenv("HITPAY_API_KEY", "")
    PRODUCTION_SALT = os.getenv("HITPAY_SALT", "")
    PRODUCTION_API_URL = "https://api.hit-pay.com/v1"
    
    # Mode: 'sandbox' or 'production'
    MODE = os.getenv("HITPAY_MODE", "sandbox")
    
    @classmethod
    def get_api_key(cls):
        """Get API key based on mode"""
        return cls.SANDBOX_API_KEY if cls.MODE == "sandbox" else cls.PRODUCTION_API_KEY
    
    @classmethod
    def get_salt(cls):
        """Get salt based on mode"""
        return cls.SANDBOX_SALT if cls.MODE == "sandbox" else cls.PRODUCTION_SALT
    
    @classmethod
    def get_api_url(cls):
        """Get API URL based on mode"""
        return cls.SANDBOX_API_URL if cls.MODE == "sandbox" else cls.PRODUCTION_API_URL
    
    @classmethod
    def is_sandbox(cls):
        """Check if in sandbox mode"""
        return cls.MODE == "sandbox"