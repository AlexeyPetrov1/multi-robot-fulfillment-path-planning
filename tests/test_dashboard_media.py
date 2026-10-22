"""Streamlit's middleware must actually serve compressed PNG responses."""

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient
from streamlit.web.server.starlette.starlette_gzip_middleware import SelectiveGZipMiddleware


@pytest.mark.parametrize("encoding", ["gzip", "identity"])
def test_dashboard_can_serve_warehouse_image(encoding):
    image = b"\x89PNG\r\n\x1a\n" + b"x" * 1024

    async def media(request):
        return Response(image, media_type="image/png")

    app = Starlette(routes=[Route("/media/warehouse.png", media)])
    app.add_middleware(SelectiveGZipMiddleware)
    with TestClient(app) as client:
        response = client.get("/media/warehouse.png", headers={"Accept-Encoding": encoding})
    assert response.status_code == 200
    assert response.content == image
    assert response.headers["content-type"] == "image/png"
