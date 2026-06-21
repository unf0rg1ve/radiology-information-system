"""Host-side proxy: bridges Docker containers to native Windows Orthanc.

Uses aiohttp for non-blocking, concurrent connections.
Listens on 0.0.0.0:8043, forwards to 127.0.0.1:8042.
"""
import aiohttp
from aiohttp import web
import urllib.parse
import os
import sys

ORTHANC_HOST = "127.0.0.1"
ORTHANC_PORT = 8042
PROXY_PORT = 8043

LOG = os.path.join(os.path.dirname(__file__) or ".", "proxy.log")


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(f"{msg}\n")
    except:
        pass


@web.middleware
async def proxy_middleware(request: web.Request, handler):
    upstream_url = f"http://{ORTHANC_HOST}:{ORTHANC_PORT}{request.path_qs}"
    body = await request.read()

    headers = {}
    for key, val in request.headers.items():
        if key.lower() not in ("host",):
            headers[key] = val

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            data=body if body else None,
        ) as resp:
            resp_body = await resp.read()
            log(f"{request.remote} {request.method} {request.path_qs} => {resp.status}")
            return web.Response(
                status=resp.status,
                body=resp_body,
                headers={k: v for k, v in resp.headers.items()
                         if k.lower() not in ("transfer-encoding", "content-encoding")},
            )


async def on_startup(app):
    log("====== PROXY STARTED ======")
    log(f"Listening on 0.0.0.0:{PROXY_PORT}")


if __name__ == "__main__":
    app = web.Application(middlewares=[proxy_middleware])
    app.on_startup.append(on_startup)
    log("Starting aiohttp proxy...")
    try:
        web.run_app(app, host="0.0.0.0", port=PROXY_PORT, print=None)
    except Exception as e:
        log(f"FATAL: {e}")
        raise
