"""
Настройки проекта «ПринтУчёт».
"""

import os                                   # ДОБАВЛЕНО
from pathlib import Path

from dotenv import load_dotenv              # ДОБАВЛЕНО

BASE_DIR = Path(__file__).resolve().parent.parent

# ДОБАВЛЕНО: читаем переменные из файла .env
load_dotenv(BASE_DIR / '.env')

# ИЗМЕНЕНО: секретный ключ и режим отладки берутся из .env
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'

# ИЗМЕНЕНО: адреса, с которых можно открыть сайт
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',                                 # ДОБАВЛЕНО: наше приложение
]
AUTH_USER_MODEL = "core.AppUser"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ИЗМЕНЕНО: вместо SQLite подключаем PostgreSQL, параметры берём из .env
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ['DB_PORT'],
    }
}


# ДОБАВЛЕНО: Argon2id первым, PBKDF2 оставлен для проверки старых хешей
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ДОБАВЛЕНО: защита сеанса (ЗИ-04)
SESSION_COOKIE_AGE = 1800            # 30 минут бездействия
SESSION_SAVE_EVERY_REQUEST = True    # отсчёт 30 минут идёт от последнего действия
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'


# ИЗМЕНЕНО: русский язык и часовой пояс
LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'          # поставь свой часовой пояс

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'


MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}