import ctypes
import ctypes.wintypes
import json
import os

STORAGE_DIR = os.path.join(os.getenv("LOCALAPPDATA", "."), "BiliSteamSign")
STORAGE_FILE = os.path.join(STORAGE_DIR, "credentials.enc")

_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_encrypt(plaintext: bytes) -> bytes:
    input_blob = _DATA_BLOB()
    input_blob.cbData = len(plaintext)
    input_blob.pbData = ctypes.create_string_buffer(plaintext, len(plaintext))
    output_blob = _DATA_BLOB()

    if not _crypt32.CryptProtectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise OSError("DPAPI encryption failed")

    encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    _kernel32.LocalFree(output_blob.pbData)
    return encrypted


def _dpapi_decrypt(ciphertext: bytes) -> bytes:
    input_blob = _DATA_BLOB()
    input_blob.cbData = len(ciphertext)
    input_blob.pbData = ctypes.create_string_buffer(ciphertext, len(ciphertext))
    output_blob = _DATA_BLOB()

    if not _crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise OSError("DPAPI decryption failed")

    plaintext = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    _kernel32.LocalFree(output_blob.pbData)
    return plaintext


class CredentialStore:
    @staticmethod
    def save(sessdata: str, bili_jct: str, dede_user_id: str):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        payload = json.dumps({
            "sessdata": sessdata,
            "bili_jct": bili_jct,
            "dede_user_id": dede_user_id,
        }).encode("utf-8")
        encrypted = _dpapi_encrypt(payload)
        with open(STORAGE_FILE, "wb") as f:
            f.write(encrypted)

    @staticmethod
    def load() -> tuple[str, str, str] | None:
        if not os.path.exists(STORAGE_FILE):
            return None
        try:
            with open(STORAGE_FILE, "rb") as f:
                encrypted = f.read()
            plaintext = _dpapi_decrypt(encrypted)
            data = json.loads(plaintext.decode("utf-8"))
            return data["sessdata"], data["bili_jct"], data["dede_user_id"]
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    @staticmethod
    def clear():
        if os.path.exists(STORAGE_FILE):
            os.remove(STORAGE_FILE)
