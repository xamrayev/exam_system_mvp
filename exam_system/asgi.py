# your_project/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_system.settings')

# Это и есть ваше ASGI-приложение, которое нужно передать Uvicorn
application = get_asgi_application()