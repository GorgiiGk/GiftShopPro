from a2wsgi import ASGIMiddleware
from web import app

application = ASGIMiddleware(app)
