from django.db import models
from django.utils.timezone import now

from django.db import models
from django.utils.timezone import now


# Create your models here.

class OwnTrackLog(models.Model):
    tid = models.CharField(max_length=100, null=False, verbose_name='User')  # 用户
    lat = models.FloatField(verbose_name='Latitude')  # 纬度
    lon = models.FloatField(verbose_name='Longitude')  # 经度
    creation_time = models.DateTimeField('Creation Time', default=now)  # 创建时间

    def __str__(self):
        return self.tid

    class Meta:
        ordering = ['creation_time']
        verbose_name = "OwnTrackLogs"  # OwnTrackLogs
        verbose_name_plural = verbose_name
        get_latest_by = 'creation_time'

# Create your models here.

class OwnTrackLog(models.Model):
    tid = models.CharField(max_length=100, null=False, verbose_name='用户')
    lat = models.FloatField(verbose_name='纬度')
    lon = models.FloatField(verbose_name='经度')
    creation_time = models.DateTimeField('创建时间', default=now)

    def __str__(self):
        return self.tid

    class Meta:
        ordering = ['creation_time']
        verbose_name = "OwnTrackLogs"
        verbose_name_plural = verbose_name
        get_latest_by = 'creation_time'
