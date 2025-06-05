from django.db import models


# Create your models here.
class commands(models.Model):
    title = models.CharField('Command Title', max_length=300)  # 命令标题
    command = models.CharField('Command', max_length=2000)  # 命令
    describe = models.CharField('Command Description', max_length=300)  # 命令描述
    creation_time = models.DateTimeField('Creation Time', auto_now_add=True)  # 创建时间
    last_modify_time = models.DateTimeField('Modification Time', auto_now=True)  # 修改时间

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Command'  # 命令
        verbose_name_plural = verbose_name


class EmailSendLog(models.Model):
    emailto = models.CharField('Recipient', max_length=300)  # 收件人
    title = models.CharField('Email Title', max_length=2000)  # 邮件标题
    content = models.TextField('Email Content')  # 邮件内容
    send_result = models.BooleanField('Result', default=False)  # 结果
    creation_time = models.DateTimeField('Creation Time', auto_now_add=True)  # 创建时间

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Email Send Log'  # 邮件发送log
        verbose_name_plural = verbose_name
        ordering = ['-creation_time']
