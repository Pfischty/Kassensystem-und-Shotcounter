"""Credentials Manager für sichere Speicherung von Passwörtern und PINs.

Verwaltet Zugangsdaten in einer separaten JSON-Datei außerhalb von Git.
Unterstützt initiale Konfiguration ohne Credentials (unlocked) und anschließende
Sperrung nach der ersten Konfiguration.
"""

import json
import os
import secrets
from pathlib import Path
from typing import Dict, Optional


class CredentialsManager:
    """Verwaltet Credentials aus einer JSON-Datei mit Fallback auf Umgebungsvariablen."""

    def __init__(self, credentials_file: str = "credentials.json"):
        """Initialize the credentials manager.
        
        Args:
            credentials_file: Path to the credentials JSON file
        """
        self.credentials_file = Path(credentials_file)
        self._cache: Optional[Dict[str, str]] = None

    def _ensure_secure_permissions(self) -> None:
        """Stellt sicher, dass die Credentials-Datei sichere Rechte hat (600)."""
        if self.credentials_file.exists():
            # On Unix systems, set permissions to 600 (read/write for owner only)
            try:
                os.chmod(self.credentials_file, 0o600)
            except (OSError, AttributeError):
                # Windows doesn't support chmod in the same way
                pass

    def _load_from_file(self) -> Optional[Dict[str, str]]:
        """Lädt Credentials aus der JSON-Datei.
        
        Returns:
            Dictionary mit Credentials oder None wenn Datei nicht existiert
        """
        if not self.credentials_file.exists():
            return None
        
        try:
            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._ensure_secure_permissions()
            return data
        except (json.JSONDecodeError, IOError) as e:
            # Log error but continue with fallback
            print(f"Warning: Could not load credentials file: {e}")
            return None

    def _save_to_file(self, data: Dict[str, str]) -> bool:
        """Speichert Credentials in die JSON-Datei.
        
        Args:
            data: Dictionary mit Credentials
            
        Returns:
            True wenn erfolgreich gespeichert
        """
        try:
            # Ensure parent directory exists
            self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write atomically by writing to temp file first
            temp_file = self.credentials_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Set secure permissions before moving
            try:
                os.chmod(temp_file, 0o600)
            except (OSError, AttributeError):
                pass
            
            # Move temp file to actual file
            temp_file.replace(self.credentials_file)
            
            # Invalidate cache
            self._cache = None
            
            return True
        except IOError as e:
            print(f"Error: Could not save credentials file: {e}")
            return False

    def get_credentials(self) -> Dict[str, str]:
        """Gibt die aktuellen Credentials zurück.
        
        Priorität:
        1. Credentials aus JSON-Datei
        2. Umgebungsvariablen (Backward compatibility)
        3. Defaults für initiales Setup
        
        Returns:
            Dictionary mit admin_username, admin_password, secret_key
        """
        # Use cache if available
        if self._cache is not None:
            return self._cache.copy()
        
        # Try to load from file
        file_creds = self._load_from_file()
        
        if file_creds:
            # File exists, use it (even if values are empty for unlocked state)
            self._cache = file_creds
            return file_creds.copy()
        
        # Fallback: Check environment variables
        env_username = os.environ.get("ADMIN_USERNAME")
        env_password = os.environ.get("ADMIN_PASSWORD")
        env_secret = os.environ.get("SECRET_KEY")
        
        # If we have env vars, migrate them to file
        if env_password or env_secret:
            creds = {
                "admin_username": env_username or "admin",
                "admin_password": env_password or "",
                "secret_key": env_secret or "",
            }
            # Don't auto-save here, let the app decide when to create the file
            self._cache = creds
            return creds.copy()
        
        # No file, no env vars -> initial unlocked state
        # Return empty credentials to allow initial setup
        default_creds = {
            "admin_username": "",
            "admin_password": "",
            "secret_key": "",
        }
        self._cache = default_creds
        return default_creds.copy()

    def update_credentials(self, admin_username: Optional[str] = None,
                          admin_password: Optional[str] = None,
                          secret_key: Optional[str] = None) -> bool:
        """Aktualisiert die Credentials und speichert sie.
        
        Args:
            admin_username: Neuer Admin-Benutzername (optional)
            admin_password: Neues Admin-Passwort (optional)
            secret_key: Neuer Secret Key (optional)
            
        Returns:
            True wenn erfolgreich gespeichert
        """
        # Get current credentials
        current = self.get_credentials()
        
        # Update with new values (only if provided)
        if admin_username is not None:
            current["admin_username"] = admin_username
        if admin_password is not None:
            current["admin_password"] = admin_password
        if secret_key is not None:
            current["secret_key"] = secret_key
        
        # Save to file
        return self._save_to_file(current)

    def is_configured(self) -> bool:
        """Prüft ob Credentials bereits konfiguriert sind.
        
        Returns:
            True wenn credentials.json existiert oder Umgebungsvariablen gesetzt sind
        """
        if self.credentials_file.exists():
            return True
        
        # Check if we have env vars as fallback
        return bool(os.environ.get("ADMIN_PASSWORD"))

    def is_unlocked(self) -> bool:
        """Prüft ob das System im unlocked State ist (kein Passwort gesetzt).
        
        Returns:
            True wenn kein Admin-Passwort gesetzt ist
        """
        creds = self.get_credentials()
        return not creds.get("admin_password")

    def generate_secret_key(self) -> str:
        """Generiert einen neuen zufälligen Secret Key.
        
        Returns:
            Hex-String mit 32 Zeichen
        """
        return secrets.token_hex(16)

    def initialize_with_defaults(self) -> bool:
        """Initialisiert Credentials mit generierten Werten.
        
        Erstellt credentials.json mit generierten Werten für initiales Setup.
        
        Returns:
            True wenn erfolgreich initialisiert
        """
        if self.is_configured():
            return False  # Already configured
        
        default_creds = {
            "admin_username": "admin",
            "admin_password": secrets.token_hex(8),  # Generate random password
            "secret_key": self.generate_secret_key(),
        }
        
        return self._save_to_file(default_creds)


# Globale Instanz für die Anwendung
credentials_manager = CredentialsManager()
