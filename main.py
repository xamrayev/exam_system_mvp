import os
import django
from pathlib import Path

# Проверяем структуру файлов
BASE_DIR = Path(__file__).resolve().parent

print("🔍 Проверка структуры файлов:")
files_to_check = [
    'manage.py',
    'exam_system/settings.py',
    'exam_system/urls.py',
    'exams/models.py',
    'exams/views.py',
    'exams/urls.py',
    'templates/base.html',
    'templates/exams/student_login.html',
    'templates/exams/exam_list.html',
]

for file_path in files_to_check:
    if (BASE_DIR / file_path).exists():
        print(f"✅ {file_path}")
    else:
        print(f"❌ {file_path} - ОТСУТСТВУЕТ!")

# Проверяем настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_system.settings')
django.setup()

from django.conf import settings
print(f"\n🔍 Проверка настроек Django:")
print(f"✅ BASE_DIR: {settings.BASE_DIR}")
print(f"✅ TEMPLATES DIRS: {settings.TEMPLATES[0]['DIRS']}")
print(f"✅ INSTALLED_APPS: {settings.INSTALLED_APPS}")

# Проверяем шаблоны
from django.template.loader import get_template
try:
    template = get_template('base.html')
    print("✅ Базовый шаблон загружается")
except:
    print("❌ Проблемы с загрузкой базового шаблона")

try:
    template = get_template('exams/student_login.html')
    print("✅ Шаблон входа загружается")
except:
    print("❌ Проблемы с загрузкой шаблона входа")