"""
Django settings for netboost project.

Generated by "django-admin startproject" using Django 4.0.5.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
"""
import os
from datetime import timedelta
from confload.confload import config
# Build paths inside the project like this: BASE_DIR / "subdir".
# BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 初始化plugins插件路径到环境变量中
# PLUGINS_PATH = os.path.join(BASE_DIR, "apps")
# sys.path.insert(0, os.path.join(PLUGINS_PATH))
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-57w6rkqxn1-)ry+sdc@3fmcd2)opcr^2a)zs^&#&-x)=fp(vb_"

# SECURITY WARNING: don"t run with debug turned on in production!
DEBUG = True if config.local_dev else False

ALLOWED_HOSTS = ["*"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netaxe.settings")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

# Application definition
INSTALLED_APPS = [
    # "captcha",
    "channels",
    # "guardian",
    # "multi_captcha_admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_celery_results.apps.CeleryResultConfig",
    "rest_framework",
    "simple_history",
    "apps.users.apps.UsersConfig",
    "apps.system.apps.SystemConfig",
    "apps.topology.apps.TopologyConfig",
    "apps.asset.apps.AssetConfig",
    "apps.automation.apps.AutomationConfig",
    "apps.dcs_control.apps.DcsControlConfig",
    "apps.config_center.apps.ConfigCenterConfig",
    # "apps.route_backend.apps.RouteBackendConfig",
    "apps.int_utilization.apps.IntUtilizationConfig",
    # 'reversion',
    'import_export',
    'django_filters',

]

DATABASES = {
    'default': {
        'NAME': config.mysql_db,
        'ENGINE': 'django.db.backends.mysql',
        'HOST': config.mysql_host,
        'USER': config.mysql_user,
        'PASSWORD': config.mysql_password,
        'PORT': config.mysql_port,
        # 'CONN_MAX_AGE': 21600,
        'ATOMIC_REQUESTS': True,
        'TEST_CHARSET': 'utf8mb4',
        'TEST_COLLATION': 'utf8mb4_general_ci',
        'TEST': {'NAME': 'net_axe_test',
                 'CHARTSET': 'utf8mb4',
                 'COLLATION': 'utf8mb4_general_ci'},
        'OPTIONS': {
            # 'charset': 'utf8mb4',
            "init_command": "SET default_storage_engine='INNODB'",
            # "init_command": "SET foreign_key_checks = 0;",
        }
    },
}

REDIS_URL = "redis://:{}@{}:{}/".format(config.redis_pwd, config.redis_host, config.redis_port)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "utils.custom.middleware.CorsMiddleWare",  # 配置跨域访问支持
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "netaxe.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# application
WSGI_APPLICATION = "netaxe.wsgi.application"
ASGI_APPLICATION = "netaxe.routing.application"

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "users.UserProfile"

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# ================================================= #
# ********************* 日志配置 ******************* #
# ================================================= #

# log 配置部分BEGIN #
if not os.path.exists(os.path.join(BASE_DIR, "logs")):
    os.makedirs(os.path.join(BASE_DIR, "logs"))

# 格式:[2020-04-22 23:33:01][micoservice.apps.ready():16] [INFO] 这是一条日志:
# 格式:[级别] [日期][模块.函数名称():行号]  信息
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "[%(asctime)s][%(name)s.%(funcName)s():%(lineno)d] [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        'standard': {
            'format': '[%(levelname)s][%(asctime)s][%(filename)s.%(funcName)s():%(lineno)d][%(message)s]',
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',  # 过滤器，只有当setting的DEBUG = True时生效
        },
    },
    "handlers": {
        "db": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "db.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,  # 最多备份5个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "server": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "server.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,  # 最多备份5个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "websocket": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "websocket.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 3,  # 最多备份5个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "webssh": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "webssh.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 3,  # 最多备份5个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "celery": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "celery.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 3,  # 最多备份3个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "automation": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "automation.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 3,  # 最多备份3个
            "formatter": "standard",
            "encoding": "utf-8",
        },
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],  # 只有在Django debug为True时才在屏幕打印日志
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
    },
    "loggers": {
        # 默认的logger应用如下配置# default日志
        '': {
            'handlers': ['console'],  # 上线之后可以把'console'移除
            'level': 'DEBUG',
            'propagate': True,  # 向不向更高级别的logger传递
        },
        "server": {
            "handlers": ["server"],
            "level": "DEBUG",
        },
        "websocket": {
            "handlers": ["websocket"],
            "level": "DEBUG",
        },
        "webssh": {
            "handlers": ["webssh"],
            "level": "DEBUG",
        },
        "django": {
            "handlers": ["server"],
            "level": "DEBUG",
        },
        "celery": {
            "handlers": ["celery"],
            "level": "DEBUG",
        },
        "automation": {
            "handlers": ["automation"],
            "level": "DEBUG",
        },
        "bus_sync": {
            "handlers": ["server"],
            "level": "DEBUG",
        },
        # 数据库相关日志
        "django.db.backends": {
            "handlers": ['db'],
            "propagate": True,
            "level": "DEBUG",
        },
        'django.utils.autoreload': {
            'handlers': [],
            'propagate': False,
        },
    },
}
TIME_FORMAT = '%Y-%m-%d %X'
# channel配置
CHANNEL_LAYERS = {
    "default": {
        # This example app uses the Redis channel layer implementation channels_redis
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["{}0".format(REDIS_URL)],
        },
    },
}
CELERY_ONCE_URL = "{}1".format(REDIS_URL)
CELERY_RESULT_BACKEND = "django-db"  # 使用django数据库
CELERY_BROKER_URL = "{}8".format(REDIS_URL)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# CELERY_RESULT_BACKEND = "redis://10.254.0.110:6379/9" #结果存储，我配置的是存储到数据库
# CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_ACCEPT_CONTENT = ["json", "application/text"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERYD_CONCURRENCY = 40  # celery worker的并发数
CELERY_MAX_TASKS_PER_CHILD = 20
CELERYD_MAX_TASKS_PER_CHILD = 20
# 这个表示每个工作的进程／线程／绿程 在执行 n 次任务后，主动销毁，之后会起一个新的。主要解决一些资源释放的问题。
CELERY_RESULT_EXPIRES = 7200  # celery任务执行结果的超时时间，
CELERY_TASK_RESULT_EXPIRES = 7200
# 这个表示保存任务结果的时长，这个时间会被设置到 redis 里面（假设 backend 是 redis ），如果抓取数据量大的话，是可以缩短保存的时间，
# 节省 backend 的资源（ redis 主要是内存）消耗，默认是 24 小时（ 86400 ），单位是秒。
CELERY_TASK_TIME_LIMIT = 7200
# 单个任务的运行时间不超过此值，否则会被SIGKILL 信号杀死
CELERY_ENABLE_UTC = False

CELERY_WORKER_CONCURRENCY = 40  # celery worker的并发数
DJANGO_CELERY_BEAT_TZ_AWARE = True
CELERY_TIMEZONE = "Asia/Shanghai"  # celery 时区问题
CELERY_TASK_TRACK_STARTED = True
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static")
]

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "/static/")
# STATIC_ROOT = "static/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    # causes verbose duplicate notifications in django 1.9
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)
# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# simple jwt 设置
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),  # access token 有效期 30分钟
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),  # refresh token 有效期 2 天
    "ROTATE_REFRESH_TOKENS": True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
APPEND_SLASH = True
# restful api 配置
REST_FRAMEWORK = {
    "DATE_FORMAT": "%Y-%m-%d",
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",  # 日期时间格式配置
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        # "rest_framework.permissions.IsAuthenticated",
        # "rest_framework.permissions.DjangoModelPermissions",
        # "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ),
    # "DEFAULT_AUTHENTICATION_CLASSES": (
    #     # "utils.authentication.auth.CustomJWTAuthentication"
    #     # "rest_framework.authentication.BasicAuthentication",
    #     # "rest_framework.authentication.SessionAuthentication",
    #     # "rest_framework.authentication.TokenAuthentication",
    #     # "rest_framework_simplejwt.authentication.JWTAuthentication",
    #     # "apps.api.authentication.ExpiringTokenAuthentication",
    # ),
    "EXCEPTION_HANDLER": "utils.custom.exception.CustomExceptionHandler",  # 自定义的异常处理
    # "EXCEPTION_HANDLER": "apps.api.tools.custom_exception.custom_exception_handler", # 自定义的异常处理
    # 下面控制分页
    "DEFAULT_PAGINATION_CLASS": "utils.custom.pagination.CustomPagination",  # 自定义分页
    # "PAGE_SIZE": 10,
    # "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.AutoSchema",
    # "DEFAULT_PAGINATION_CLASS": "apps.api.tools.custom_pagination.LargeResultsSetPagination",
    # "UNAUTHENTICATED_USER": None
}

# Restful token 有效时间60分钟
REST_FRAMEWORK_TOKEN_EXPIRE_MINUTES = 60 * 8
# 设置上传请求的最大字节
DATA_UPLOAD_MAX_MEMORY_SIZE = 30485760

# api 缓存配置
REST_FRAMEWORK_EXTENSIONS = {
    "DEFAULT_CACHE_RESPONSE_TIMEOUT": 60 * 60,
    "DEFAULT_USE_CACHE": "api_cache",
    "DEFAULT_OBJECT_CACHE_KEY_FUNC": "rest_framework_extensions.utils.default_object_cache_key_func",
    "DEFAULT_LIST_CACHE_KEY_FUNC": "rest_framework_extensions.utils.default_list_cache_key_func",
}

# REST API REDIS缓存配置
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "{}2".format(REDIS_URL),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        }
    },
    "api_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "{}3".format(REDIS_URL),
        # "TIMEOUT": 7 * 24 * 60 * 60,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# 认证配置
AUTHENTICATION_BACKENDS = (
    # "django_auth_ldap.backend.LDAPBackend",
    # "utils.custom.backends.CustomBackend",
    "django.contrib.auth.backends.ModelBackend",
    # "guardian.backends.ObjectPermissionBackend",  # 这是guardian的
)

# ================================================= #
# **************** 验证码配置  ********************* #
# ================================================= #
# MULTI_CAPTCHA_ADMIN = {
#     "engine": "simple-captcha",
# }
# CAPTCHA_IMAGE_SIZE = (160, 60)  # 设置 captcha 图片大小
# CAPTCHA_LENGTH = 4  # 字符个数
# CAPTCHA_TIMEOUT = 1  # 超时(minutes)
# CAPTCHA_OUTPUT_FORMAT = "%(image)s %(text_field)s %(hidden_field)s "
# CAPTCHA_FONT_SIZE = 40  # 字体大小
# CAPTCHA_FOREGROUND_COLOR = "#64DAAA"  # 前景色
# CAPTCHA_BACKGROUND_COLOR = "#F5F7F4"  # 背景色
# CAPTCHA_NOISE_FUNCTIONS = (
#     "captcha.helpers.noise_arcs",  # 线
#     # "captcha.helpers.noise_dots",  # 点
# )
# CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.random_char_challenge" #字母验证码
# CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.math_challenge"  # 加减乘除验证码

# ================================================= #
# **************** swagger  *********************** #
# ================================================= #
SWAGGER_SETTINGS = {
    # 基础样式
    "SECURITY_DEFINITIONS": {"basic": {"type": "basic"}},
    # 如果需要登录才能够查看接口文档, 登录的链接使用restframework自带的.
    # "LOGIN_URL": "apiLogin/",
    "LOGIN_URL": "rest_framework:login",
    "LOGOUT_URL": "rest_framework:logout",
    # "DOC_EXPANSION": None,
    # "SHOW_REQUEST_HEADERS":True,
    # "USE_SESSION_AUTH": True,
    # "DOC_EXPANSION": "list",
    # 接口文档中方法列表以首字母升序排列
    "APIS_SORTER": "alpha",
    # 如果支持json提交, 则接口文档中包含json输入框
    "JSON_EDITOR": True,
    # 方法列表字母排序
    "OPERATIONS_SORTER": "alpha",
    "VALIDATOR_URL": None,
    "AUTO_SCHEMA_TYPE": 2,  # 分组根据url层级分，0、1 或 2 层
    "DEFAULT_AUTO_SCHEMA_CLASS": "utils.custom.swagger.CustomSwaggerAutoSchema",
}

# ================================================= #
# ******************** 其他配置 ******************** #
# ================================================= #
API_LOG_ENABLE = True
API_LOG_METHODS = 'ALL'
# API_LOG_METHODS = ["POST", "UPDATE", "DELETE", "PUT"]
