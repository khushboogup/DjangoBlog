import logging
import os

import openai

from servermanager.models import commands

logger = logging.getLogger(__name__)

openai.api_key = os.environ.get('OPENAI_API_KEY')
if os.environ.get('HTTP_PROXY'):
    openai.proxy = os.environ.get('HTTP_PROXY')


class ChatGPT:

    @staticmethod
    def chat(prompt):
        try:
            completion = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                      messages=[{"role": "user", "content": prompt}])
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(e)
            return "Server error"  # 服务器出错了


class CommandHandler:
    def __init__(self):
        self.commands = commands.objects.all()

    def run(self, title):
        """
        Run command
        :param title: Command
        :return: Return the result of the command execution
        """
        cmd = list(
            filter(
                lambda x: x.title.upper() == title.upper(),
                self.commands))
        if cmd:
            return self.__run_command__(cmd[0].command)
        else:
            return "No related command found, please type 'helpme' for assistance."  # 未找到相关命令，请输入hepme获得帮助。

    def __run_command__(self, cmd):
        try:
            res = os.popen(cmd).read()
            return res
        except BaseException:
            return 'Command execution failed!'  # 命令执行出错!

    def get_help(self):
        rsp = ''
        for cmd in self.commands:
            rsp += '{c}:{d}\n'.format(c=cmd.title, d=cmd.describe)
        return rsp


if __name__ == '__main__':
    chatbot = ChatGPT()
    prompt = "Write a 1000-word essay on AI"  # 写一篇1000字关于AI的论文
    print(chatbot.chat(prompt))
