from django.db import models

# Create your models here.


class GraphToGrafana(models.Model):
    title = models.CharField(verbose_name="标题", max_length=200, null=True, blank=True)
    config = models.CharField(verbose_name="图形配置参数", max_length=200, null=True, blank=True)
    columns = models.IntegerField(verbose_name="占用列数", default=4)
    is_min = models.BooleanField(verbose_name="是否最小化", default=False)
    query = models.TextField(verbose_name="查询请求参数", null=True, blank=True)



