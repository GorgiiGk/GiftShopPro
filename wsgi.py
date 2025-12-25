from a2wsgi import ASGIMiddleware
from web import app

# PythonAnywhere ждёт WSGI callable под именем "application"
application = ASGIMiddleware(app)
