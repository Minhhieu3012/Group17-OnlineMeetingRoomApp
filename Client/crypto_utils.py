# filename: crypto_utils.py
import json, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class AESBox:
    def __init__(self, key: bytes):
        assert len(key) in (16, 24, 32)
        self.key = key
        self.aes = AESGCM(key)

    def encrypt_message(self, obj: dict) -> dict:
        nonce = os.urandom(12)
        data = json.dumps(obj, separators=(",", ":")).encode()
        ct = self.aes.encrypt(nonce, data, None)
        return {"enc": True,
                "alg": "AESGCM",
                "n": base64.b64encode(nonce).decode(),
                "ct": base64.b64encode(ct).decode()}

    def decrypt_message(self, obj: dict) -> dict:
        nonce = base64.b64decode(obj["n"])    
        ct = base64.b64decode(obj["ct"]) 
        pt = self.aes.decrypt(nonce, ct, None)
        return json.loads(pt.decode())
