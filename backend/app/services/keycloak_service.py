"""
Keycloak service for authentication and authorization
Replaces Firebase auth with Keycloak JWT verification
"""
import logging
from typing import Optional, Dict, List
from functools import lru_cache

import requests
from jose import jwt, jwk

from ..config.settings import settings

logger = logging.getLogger(__name__)


class KeycloakService:
    """Service for Keycloak JWT verification and user management"""

    def __init__(self):
        # Normalize server URL to avoid double slashes in issuer
        self.server_url = settings.KEYCLOAK_SERVER_URL.rstrip("/")
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET
        self.allowed_audiences = settings.KEYCLOAK_AUDIENCES or [self.client_id]
        self.issuer_url = f"{self.server_url}/realms/{self.realm}"
        self.jwks_url = f"{self.issuer_url}/protocol/openid-connect/certs"

    @lru_cache(maxsize=1)
    def get_jwks(self) -> Dict:
        """Get JWKS (JSON Web Key Set) from Keycloak"""
        try:
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from Keycloak: {str(e)}")
            raise

    def get_jwk_key(self, token: str) -> Optional[Dict]:
        """Get the appropriate JWK for a token"""
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                logger.error("Token header missing 'kid'")
                return None

            jwks = self.get_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    return key

            logger.error(f"JWK with kid={kid} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting JWK: {str(e)}")
            return None

    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode Keycloak JWT token
        Returns decoded token payload if valid, None otherwise
        """
        try:
            jwk_key_dict = self.get_jwk_key(token)
            if not jwk_key_dict:
                return None

            key = jwk.construct(jwk_key_dict)

            # Decode without audience verification first, then check manually
            # This allows us to handle multiple valid audiences
            decode_options = {
                "verify_signature": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_aud": False,  # We'll check audience manually
            }

            decode_kwargs = {
                "algorithms": ["RS256"],
                "issuer": self.issuer_url,
                "options": decode_options,
            }

            decoded_token = jwt.decode(token, key, **decode_kwargs)
            
            # Manually verify audience
            token_aud = decoded_token.get("aud")
            if isinstance(token_aud, str):
                token_aud = [token_aud]
            
            if self.allowed_audiences and not any(aud in self.allowed_audiences for aud in token_aud):
                logger.warning(f"Token audience {token_aud} not in allowed audiences {self.allowed_audiences}")
                return None
            return decoded_token
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.JWTClaimsError as e:
            logger.warning(f"JWT claims error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def get_user_id(self, token: str) -> Optional[str]:
        """Extract user ID (sub) from token"""
        decoded = self.verify_token(token)
        if decoded:
            return decoded.get("sub")
        return None

    def get_user_roles(self, token: str) -> List[str]:
        """Extract user roles from token"""
        decoded = self.verify_token(token)
        if not decoded:
            return []

        realm_access = decoded.get("realm_access", {})
        roles = realm_access.get("roles", [])
        return roles

    def get_user_email(self, token: str) -> Optional[str]:
        """Extract user email from token"""
        decoded = self.verify_token(token)
        if decoded:
            return decoded.get("email")
        return None

    def has_role(self, token: str, role: str) -> bool:
        """Check if user has a specific role"""
        roles = self.get_user_roles(token)
        return role in roles


# Create global instance
keycloak_service = KeycloakService()

