from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
import dj_database_url
import os
from assessment.services.google_storage import setup_google_storage_credentials


load_dotenv()
setup_google_storage_credentials()


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-m!=vw$!g^85#yna0&*sgn^9c9881f*9dk5w!7h-c(s!ja38um%'

ALLOWED_HOSTS = ['*']
CORS_ALLOW_HEADERS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
CLOUDRUN_SERVICE_URL = os.getenv('CLOUDRUN_SERVICE_URL')

if CLOUDRUN_SERVICE_URL:
    ALLOWED_HOSTS.append(urlparse(CLOUDRUN_SERVICE_URL))
    CSRF_TRUSTED_ORIGINS = [CLOUDRUN_SERVICE_URL]
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = not CLOUDRUN_SERVICE_URL

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',
    'polymorphic',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    'main',
    'users',
    'assessee',
    'assessor',
    'assessment',
    'company',
    'video_conference'
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'EXCEPTION_HANDLER': 'one_day_intern.exception_config.custom_exception_handler'
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=100),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

ROOT_URLCONF = 'one_day_intern.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'one_day_intern.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(conn_max_age=600)
}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

QUIZ_BASE_DURATION = 30
SUBMISSION_BUFFER_TIME_IN_SECONDS = 10

# Settings for Google Auth Login and Registration
AUTH_USER_MODEL = 'users.OdiUser'
GOOGLE_AUTH_CLIENT_ID = os.getenv('CLIENT_ID')
GOOGLE_AUTH_CLIENT_SECRET = os.getenv('CLIENT_SECRET')
GOOGLE_AUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token?'
GOOGLE_AUTH_GRANT_TYPE = 'authorization_code'
GOOGLE_AUTH_LOGIN_REDIRECT_URI = os.getenv('GOOGLE_AUTH_LOGIN_REDIRECT_URI')
GOOGLE_AUTH_REGISTER_ASSESSEE_REDIRECT_URI = os.getenv('GOOGLE_AUTH_REGISTER_ASSESSEE_REDIRECT_URI')
GOOGLE_AUTH_CLIENT_CALLBACK_URL = os.getenv('GOOGLE_AUTH_CLIENT_CALLBACK_URL')

ASSESSOR_FE_REGISTRATION_URL = os.getenv('ASSESSOR_FE_REGISTRATION_URL', default='')

# Settings for Automatic Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
SERVER_EMAIL = os.getenv('SERVER_EMAIL')

# Google Storage
GOOGLE_BUCKET_BASE_DIRECTORY = '/submissions'
GOOGLE_STORAGE_BUCKET_NAME = 'one-day-intern-bucket'