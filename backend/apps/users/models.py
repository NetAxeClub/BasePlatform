import hashlib
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class UserProfile(AbstractUser):
    username = models.CharField(
        max_length=150, unique=True, db_index=True, verbose_name="用户账号", help_text="用户账号")
    nick_name = models.CharField(
        max_length=30, null=True, blank=True, verbose_name='昵称')
    mobile = models.CharField(max_length=11, null=True,
                              blank=True, verbose_name='手机号码')
    email = models.EmailField(
        max_length=255, verbose_name="邮箱", null=True, blank=True, help_text="邮箱")
    image = models.ImageField(
        upload_to='images/%Y/%m/%d/', default='images/default.png', max_length=100)
    login_status = (
        (0, '在线'),
        (1, '离线'),
        (2, '忙碌'),
    )
    login_status = models.SmallIntegerField(
        choices=login_status, default=0, verbose_name='登录状态')
    GENDER_CHOICES = (
        (0, "未知"),
        (1, "男"),
        (2, "女"),
    )
    gender = models.IntegerField(
        choices=GENDER_CHOICES, default=0, verbose_name="性别", null=True, blank=True, help_text="性别"
    )
    USER_TYPE = (
        (0, "后台用户"),
        (1, "前台用户"),
    )
    user_type = models.IntegerField(
        choices=USER_TYPE, default=0, verbose_name="用户类型", null=True, blank=True, help_text="用户类型"
    )
    jwt_secret = models.UUIDField(default=uuid.uuid4)

    def jwt_get_secret_key(self):
        return self.jwt_secret

    def get_login_status(self):
        return self.login_status

    def set_password(self, raw_password):
        super().set_password(hashlib.md5(raw_password.encode(encoding="UTF-8")).hexdigest())

    class Meta:
        db_table = 'ops_user'
        verbose_name = '用户表'
        verbose_name_plural = '用户表'


# class Organization(models.Model):
#     name = models.CharField(verbose_name='组织名称',
#                             max_length=20, null=False, unique=True)
#
#     def __str__(self):
#         return self.name
#
#     class Meta:
#         db_table = 'organization'  # 通过db_table自定义数据表名
#         verbose_name = '组织表'
#         verbose_name_plural = '组织表'
#         indexes = [models.Index(fields=['name', ]), ]
