import logging
import os
import re

import jsonpickle
from django.conf import settings
from werobot import WeRoBot
from werobot.replies import ArticlesReply, Article
from werobot.session.filestorage import FileStorage

from djangoblog.utils import get_sha256
from servermanager.api.blogapi import BlogApi
from servermanager.api.commonapi import ChatGPT, CommandHandler
from .MemcacheStorage import MemcacheStorage

robot = WeRoBot(token=os.environ.get('DJANGO_WEROBOT_TOKEN')
                      or 'lylinux', enable_session=True)
memstorage = MemcacheStorage()
if memstorage.is_available:
    robot.config['SESSION_STORAGE'] = memstorage
else:
    if os.path.exists(os.path.join(settings.BASE_DIR, 'werobot_session')):
        os.remove(os.path.join(settings.BASE_DIR, 'werobot_session'))
    robot.config['SESSION_STORAGE'] = FileStorage(filename='werobot_session')

blogapi = BlogApi()
cmd_handler = CommandHandler()
logger = logging.getLogger(__name__)


def convert_to_article_reply(articles, message):
    reply = ArticlesReply(message=message)
    from blog.templatetags.blog_tags import truncatechars_content
    for post in articles:
        imgs = re.findall(r'(?:http\:|https\:)?\/\/.*\.(?:png|jpg)', post.body)
        imgurl = ''
        if imgs:
            imgurl = imgs[0]
        article = Article(
            title=post.title,
            description=truncatechars_content(post.body),
            img=imgurl,
            url=post.get_full_url()
        )
        reply.add_article(article)
    return reply


@robot.filter(re.compile(r"^\?.*"))
def search(message, session):
    s = message.content
    searchstr = str(s).replace('?', '')
    result = blogapi.search_articles(searchstr)
    if result:
        articles = list(map(lambda x: x.object, result))
        reply = convert_to_article_reply(articles, message)
        return reply
    else:
        return 'No related articles found.'  # 没有找到相关文章。


@robot.filter(re.compile(r'^category\s*$', re.I))
def category(message, session):
    categorys = blogapi.get_category_lists()
    content = ','.join(map(lambda x: x.name, categorys))
    return 'All article categories: ' + content  # 所有文章分类目录：


@robot.filter(re.compile(r'^recent\s*$', re.I))
def recents(message, session):
    articles = blogapi.get_recent_articles()
    if articles:
        reply = convert_to_article_reply(articles, message)
        return reply
    else:
        return "No articles yet."  # 暂时还没有文章


@robot.filter(re.compile('^help$', re.I))
def help(message, session):
    return '''Welcome!
            By default, you will chat with the Turing robot~~
        You can use the following commands to get information:
        ?keyword search articles.
        For example, ?python.
        category to get the article category list and article count.
        category-*** to get articles of a category.
        For example, category-python.
        recent to get the latest articles.
        help to get help.
        weather: to get weather information.
        For example, weather:Xi'an.
        idcard: to get ID card information.
        For example, idcard:61048119xxxxxxxxxx.
        music: music search.
        For example, music:Cloudy Happiness.
        PS: Punctuation marks above should not be Chinese punctuation~~
        '''


@robot.filter(re.compile(r'^weather\:.*$', re.I))
def weather(message, session):
    return "Under construction..."  # 建设中...


@robot.filter(re.compile(r'^idcard\:.*$', re.I))
def idcard(message, session):
    return "Under construction..."  # 建设中...


@robot.handler
def echo(message, session):
    handler = MessageHandler(message, session)
    return handler.handler()


class MessageHandler:
    def __init__(self, message, session):
        userid = message.source
        self.message = message
        self.session = session
        self.userid = userid
        try:
            info = session[userid]
            self.userinfo = jsonpickle.decode(info)
        except Exception as e:
            userinfo = WxUserInfo()
            self.userinfo = userinfo

    @property
    def is_admin(self):
        return self.userinfo.isAdmin

    @property
    def is_password_set(self):
        return self.userinfo.isPasswordSet

    def save_session(self):
        info = jsonpickle.encode(self.userinfo)
        self.session[self.userid] = info

    def handler(self):
        info = self.message.content

        if self.userinfo.isAdmin and info.upper() == 'EXIT':
            self.userinfo = WxUserInfo()
            self.save_session()
            return "Exit successful"  # 退出成功
        if info.upper() == 'ADMIN':
            self.userinfo.isAdmin = True
            self.save_session()
            return "Enter the admin password"  # 输入管理员密码
        if self.userinfo.isAdmin and not self.userinfo.isPasswordSet:
            passwd = settings.WXADMIN
            if settings.TESTING:
                passwd = '123'
            if passwd.upper() == get_sha256(get_sha256(info)).upper():
                self.userinfo.isPasswordSet = True
                self.save_session()
                return "Validation passed, please enter a command or code to execute: enter helpme for help"  # 验证通过,请输入命令或者要执行的命令代码:输入helpme获得帮助
            else:
                if self.userinfo.Count >= 3:
                    self.userinfo = WxUserInfo()
                    self.save_session()
                    return "Exceeded validation attempts"  # 超过验证次数
                self.userinfo.Count += 1
                self.save_session()
                return "Validation failed, please re-enter the admin password:"  # 验证失败，请重新输入管理员密码:
        if self.userinfo.isAdmin and self.userinfo.isPasswordSet:
            if self.userinfo.Command != '' and info.upper() == 'Y':
                return cmd_handler.run(self.userinfo.Command)
            else:
                if info.upper() == 'HELPME':
                    return cmd_handler.get_help()
                self.userinfo.Command = info
                self.save_session()
                return "Confirm execution: " + info + " command?"  # 确认执行: 命令?

        return ChatGPT.chat(info)


class WxUserInfo():
    def __init__(self):
        self.isAdmin = False
        self.isPasswordSet = False
        self.Count = 0
        self.Command = ''
