from a2wsgi import ASGIMiddleware
from web import app as fastapi_app

# ✅ WSGI app для PythonAnywhere
application = ASGIMiddleware(fastapi_app)
