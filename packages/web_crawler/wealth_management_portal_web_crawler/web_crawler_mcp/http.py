"""
HTTP entry point for the Web Crawler MCP server.

Includes RequestDecompressionMiddleware to handle an AgentCore proxy issue where
request bodies arrive with an unknown encoding (not gzip/deflate/zlib) that causes
UnicodeDecodeError in the MCP SDK's json.loads(body) call. The middleware logs
diagnostic hex dumps and attempts automatic decompression.
"""

import gzip
import logging
import os
import zlib

from .server import mcp

logger = logging.getLogger(__name__)


class RequestDecompressionMiddleware:
    """ASGI middleware that decompresses request bodies for the MCP SDK.

    AgentCore proxy sends compressed/encoded bodies without standard
    Content-Encoding headers, causing UnicodeDecodeError in the MCP SDK.
    This middleware intercepts HTTP requests, logs diagnostics, and
    attempts decompression before forwarding to the app.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract headers for diagnostics
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        content_encoding = headers.get("content-encoding", "")

        # Collect full body from potentially chunked messages
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break

        logger.warning(
            "MCP request: Content-Type=%s Content-Encoding=%s body_len=%d first_64_hex=%s",
            headers.get("content-type", ""),
            content_encoding,
            len(body),
            body[:64].hex(),
        )

        # Attempt decompression
        if body:
            decompressed = self._decompress(body, content_encoding)
            if decompressed is not None:
                body = decompressed

        # Create a new receive that returns the (possibly decompressed) body
        body_sent = False

        async def patched_receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            # After body is sent, pass through for disconnect etc.
            return await receive()

        await self.app(scope, patched_receive, send)

    def _decompress(self, body, content_encoding):
        """Try to decompress body. Returns decompressed bytes or None."""
        encoding = content_encoding.strip().lower()

        if encoding == "gzip":
            return self._try(gzip.decompress, body, "gzip (header)")

        if encoding in ("deflate", "zlib"):
            return self._try(zlib.decompress, body, "zlib (header)")

        # No Content-Encoding — check if body is valid UTF-8 already
        try:
            body.decode("utf-8")
            return None  # Already valid, no decompression needed
        except UnicodeDecodeError:
            pass

        # Try common decompression methods as fallback
        for name, fn in [
            ("gzip", gzip.decompress),
            ("zlib", zlib.decompress),
            ("raw-deflate", lambda b: zlib.decompress(b, -zlib.MAX_WBITS)),
        ]:
            result = self._try(fn, body, name)
            if result is not None:
                return result

        logger.warning("All decompression attempts failed, passing through original body")
        return None

    def _try(self, fn, body, name):
        try:
            result = fn(body)
            logger.warning("Decompressed body with %s: %d -> %d bytes", name, len(body), len(result))
            return result
        except Exception:
            return None


if __name__ == "__main__":
    import uvicorn

    app = mcp.streamable_http_app()
    app = RequestDecompressionMiddleware(app)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
