"""API client for Nowledge Mem server"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Success status codes
SUCCESS_CODES = frozenset({200, 201, 202, 204})


class APIError(Exception):
    """Raised when API request fails

    Attributes:
        status_code: HTTP status code (if available)
        response_text: Response body (if available)
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class APIClient:
    """HTTP client for Nowledge Mem API

    Uses connection pooling via httpx.Client for better performance.
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str,
        timeout_health: float = 5.0,
        timeout_request: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout_health = timeout_health
        self.timeout_request = timeout_request
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client with connection pooling"""
        if self._client is None:
            self._client = httpx.Client(
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                },
                # Connection pooling settings
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    def close(self):
        """Close the HTTP client and release connections"""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def health_check(self) -> tuple[bool, str | None]:
        """Check API health endpoint

        Returns:
            Tuple of (is_healthy, error_message)
            - (True, None) if healthy
            - (False, "error description") if unhealthy
        """
        client = self._get_client()
        try:
            response = client.get(
                f"{self.base_url}/health",
                timeout=self.timeout_health,
            )
            if response.status_code == 200:
                return True, None
            else:
                return False, f"Health check returned {response.status_code}"

        except httpx.TimeoutException:
            error = f"Health check timeout after {self.timeout_health}s"
            logger.warning(error)
            return False, error

        except httpx.ConnectError as e:
            error = f"Connection failed: {e}"
            logger.warning(error)
            return False, error

        except httpx.RequestError as e:
            error = f"Request error: {type(e).__name__}: {e}"
            logger.warning(error)
            return False, error

    def auth_check(self) -> tuple[bool, str | None]:
        """Verify authentication by attempting a minimal authenticated request

        Returns:
            Tuple of (is_authenticated, error_message)
        """
        client = self._get_client()
        try:
            # Try to access an authenticated endpoint
            # Most APIs have a /me or /user endpoint for this
            response = client.get(
                f"{self.base_url}/threads",
                params={"limit": 1},
                timeout=self.timeout_health,
            )

            if response.status_code == 401:
                return False, "Authentication failed: invalid or expired token"
            if response.status_code == 403:
                return False, "Authorization failed: insufficient permissions"
            if response.status_code in SUCCESS_CODES:
                return True, None

            # Other status codes - might still be authenticated
            return True, f"Auth check returned {response.status_code} (may be OK)"

        except httpx.TimeoutException:
            return False, f"Auth check timeout after {self.timeout_health}s"
        except httpx.RequestError as e:
            return False, f"Auth check failed: {type(e).__name__}: {e}"

    def save_thread(
        self,
        payload: dict[str, Any],
        retry_count: int = 1,
    ) -> dict[str, Any]:
        """Save thread to Nowledge Mem

        Args:
            payload: Thread request payload
            retry_count: Number of retries on transient failures (default: 1)

        Returns:
            API response data

        Raises:
            APIError: If request fails after all retries
        """
        client = self._get_client()
        last_error: APIError | None = None

        for attempt in range(retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{retry_count}")

                response = client.post(
                    f"{self.base_url}/threads",
                    json=payload,
                    timeout=self.timeout_request,
                )

                if response.status_code in SUCCESS_CODES:
                    # Handle 204 No Content
                    if response.status_code == 204:
                        return {"status": "success", "thread": payload}
                    return response.json()

                # Non-retryable errors
                if response.status_code in (400, 401, 403, 404, 422):
                    raise APIError(
                        f"API error {response.status_code}: {response.text[:500]}",
                        status_code=response.status_code,
                        response_text=response.text,
                    )

                # Retryable server errors (5xx)
                last_error = APIError(
                    f"Server error {response.status_code}: {response.text[:200]}",
                    status_code=response.status_code,
                    response_text=response.text,
                )
                logger.warning(f"Retryable error: {last_error}")

            except httpx.TimeoutException as e:
                last_error = APIError(
                    f"Request timeout after {self.timeout_request}s: {e}"
                )
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")

            except httpx.ConnectError as e:
                last_error = APIError(f"Connection failed: {e}")
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")

            except httpx.RequestError as e:
                last_error = APIError(f"Request failed: {type(e).__name__}: {e}")
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")

        # All retries exhausted
        raise last_error or APIError("Unknown error after retries")
