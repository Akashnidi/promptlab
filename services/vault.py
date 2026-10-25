import base64
import hashlib
import json
import os
import secrets as secrets_module
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class Vault:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)

    def _read_vault(self) -> dict:
        if not self.vault_path.exists():
            return {}
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_vault(self, data: dict) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def is_initialized(self) -> bool:
        """Check if .vault.json exists and has a password_hash field."""
        if not self.vault_path.exists():
            return False
        data = self._read_vault()
        return bool(data.get("password_hash"))

    def setup_master_password(self, password: str) -> None:
        """Generate auth & encryption salts, hash password, and initialize vault."""
        auth_salt = os.urandom(32)
        enc_salt = os.urandom(32)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=auth_salt,
            iterations=100_000,
        )
        password_hash = kdf.derive(password.encode("utf-8")).hex()

        vault_data = {
            "auth_salt": auth_salt.hex(),
            "password_hash": password_hash,
            "enc_salt": enc_salt.hex(),
            "secrets": {},
        }
        self._write_vault(vault_data)

    def verify_master_password(self, password: str) -> bool:
        """Load auth_salt and password_hash from vault and verify password."""
        if not self.is_initialized():
            return False
        data = self._read_vault()
        auth_salt_hex = data.get("auth_salt")
        expected_hash_hex = data.get("password_hash")
        if not auth_salt_hex or not expected_hash_hex:
            return False

        try:
            auth_salt = bytes.fromhex(auth_salt_hex)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=auth_salt,
                iterations=100_000,
            )
            derived_hash_hex = kdf.derive(password.encode("utf-8")).hex()
            return secrets_module.compare_digest(derived_hash_hex, expected_hash_hex)
        except Exception:
            return False

    def _derive_fernet_key(self, password: str) -> Fernet:
        """Derive 32 bytes from enc_salt + password and return Fernet cipher."""
        data = self._read_vault()
        enc_salt_hex = data.get("enc_salt")
        if not enc_salt_hex:
            raise ValueError("Vault is not properly initialized with encryption salt.")

        enc_salt = bytes.fromhex(enc_salt_hex)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=enc_salt,
            iterations=100_000,
        )
        derived_bytes = kdf.derive(password.encode("utf-8"))
        fernet_key = base64.urlsafe_b64encode(derived_bytes)
        return Fernet(fernet_key)

    def store_secret(self, password: str, provider: str, api_key: str) -> None:
        """Verify password, encrypt api_key, and save to vault secrets."""
        if not self.verify_master_password(password):
            raise ValueError("Invalid master password")

        provider_key = provider.strip().lower()
        fernet = self._derive_fernet_key(password)
        encrypted_val = fernet.encrypt(api_key.strip().encode("utf-8")).decode("utf-8")

        data = self._read_vault()
        secrets = data.setdefault("secrets", {})
        secrets[provider_key] = encrypted_val
        self._write_vault(data)

    def get_secret(self, password: str, provider: str) -> Optional[str]:
        """Verify password and return decrypted api_key or None if not found."""
        if not self.verify_master_password(password):
            raise ValueError("Invalid master password")

        data = self._read_vault()
        provider_key = provider.strip().lower()
        encrypted_val = data.get("secrets", {}).get(provider_key)
        if not encrypted_val:
            return None

        fernet = self._derive_fernet_key(password)
        decrypted_val = fernet.decrypt(encrypted_val.encode("utf-8")).decode("utf-8")
        return decrypted_val

    def list_providers(self) -> list[str]:
        """Return list of stored provider names without decryption."""
        if not self.is_initialized():
            return []
        data = self._read_vault()
        return list(data.get("secrets", {}).keys())

    def delete_secret(self, password: str, provider: str) -> None:
        """Verify password and remove provider key from secrets."""
        if not self.verify_master_password(password):
            raise ValueError("Invalid master password")

        provider_key = provider.strip().lower()
        data = self._read_vault()
        secrets = data.get("secrets", {})
        if provider_key in secrets:
            del secrets[provider_key]
            data["secrets"] = secrets
            self._write_vault(data)
