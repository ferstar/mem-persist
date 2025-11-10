"""API client for Nowledge Mem server"""

import httpx
from typing import Any


class APIError(Exception):
    """Raised when API request fails"""
    pass


class APIClient:
    """HTTP client for Nowledge Mem API"""

    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    def _headers(self) -> dict[str, str]:
        """Build request headers"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    def health_check(self) -> bool:
        """Check API health endpoint

        Returns:
            True if API is reachable and healthy
        """
        try:
            response = httpx.get(
                f"{self.base_url}/health",
                headers=self._headers(),
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    def save_thread(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Save thread to Nowledge Mem

        Args:
            payload: Thread request payload

        Returns:
            API response data

        Raises:
            APIError: If request fails
        """
        try:
            response = httpx.post(
                f"{self.base_url}/threads",
                headers=self._headers(),
                json=payload,
                timeout=30.0,
            )

            if response.status_code not in (200, 201):
                raise APIError(
                    f"API returned {response.status_code}: {response.text[:200]}"
                )

            return response.json()

        except httpx.TimeoutException as e:
            raise APIError(f"Request timeout: {e}")
        except httpx.RequestError as e:
            raise APIError(f"Request failed: {e}")
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")
