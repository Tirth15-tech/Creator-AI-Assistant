import sys
sys.path.insert(0, 'E:/creator_AIassistance')
from app.main import app
print("Routes loaded:")
for route in app.routes:
    if hasattr(route, 'path'):
        methods = getattr(route, "methods", set())
        print(f"  {methods} {route.path}")
print("Total routes:", len(list(app.routes)))
