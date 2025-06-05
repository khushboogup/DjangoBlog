import os
import requests

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.paginator import Paginator
from django.templatetags.static import static
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import BlogUser
from blog.forms import BlogSearchForm
from blog.models import Article, Category, Tag, SideBar, Links
from blog.templatetags.blog_tags import load_pagination_info, load_articletags
from djangoblog.utils import get_current_site, get_sha256, save_user_avatar, send_email
from djangoblog.spider_notify import SpiderNotify
from oauth.models import OAuthUser, OAuthConfig
from blog.templatetags.blog_tags import gravatar_url, gravatar
from blog.documents import ELASTICSEARCH_ENABLED


class ArticleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = BlogUser.objects.get_or_create(
            email="liangliangyy@gmail.com",
            username="liangliangyy")[0]
        self.user.set_password("liangliangyy")
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

    def test_article_creation_and_views(self):
        """Test article creation, category/tag association, and related views."""
        site_domain = get_current_site().domain

        # Sidebar
        SideBar.objects.create(name='Test Sidebar', content='Content', is_enable=True, sequence=1)

        # Category & Tag
        category = Category.objects.create(name="Test Category", creation_time=timezone.now(),
                                           last_mod_time=timezone.now())
        tag = Tag.objects.create(name="Test Tag")

        # Create an article
        article = Article.objects.create(
            title="Test Title",
            body="Test Content",
            author=self.user,
            category=category,
            type='a',
            status='p'
        )
        self.assertEqual(article.tags.count(), 0)
        article.tags.add(tag)
        self.assertEqual(article.tags.count(), 1)

        # Create multiple articles
        for i in range(20):
            a = Article.objects.create(
                title=f"Title {i}",
                body=f"Content {i}",
                author=self.user,
                category=category,
                type='a',
                status='p'
            )
            a.tags.add(tag)

        if ELASTICSEARCH_ENABLED:
            call_command("build_index")
            response = self.client.get('/search', {'q': 'Title'})
            self.assertEqual(response.status_code, 200)

        # Test views
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)
        SpiderNotify.notify(article.get_absolute_url())

        self.assertEqual(self.client.get(tag.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(category.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get('/search', {'q': 'django'}).status_code, 200)

        self.assertIsNotNone(load_articletags(article))

        # Test login and archive view
        self.client.login(username='liangliangyy', password='liangliangyy')
        self.assertEqual(self.client.get(reverse('blog:archives')).status_code, 200)

        # Test pagination
        self.check_pagination(Paginator(Article.objects.all(), settings.PAGINATE_BY), '', '')
        self.check_pagination(Paginator(Article.objects.filter(tags=tag), settings.PAGINATE_BY), '分类标签归档', tag.slug)
        self.check_pagination(Paginator(Article.objects.filter(author=self.user), settings.PAGINATE_BY), '作者文章归档', self.user.username)
        self.check_pagination(Paginator(Article.objects.filter(category=category), settings.PAGINATE_BY), '分类目录归档', category.slug)

        # Search form
        BlogSearchForm().search()

        # Send spider notify to Baidu
        SpiderNotify.baidu_notify([article.get_full_url()])

        # Gravatar
        gravatar_url('liangliangyy@gmail.com')
        gravatar('liangliangyy@gmail.com')

        # Links
        Links.objects.create(sequence=1, name="lylinux", link='https://www.lylinux.net')
        self.assertEqual(self.client.get('/links.html').status_code, 200)

        # RSS & sitemap
        self.assertEqual(self.client.get('/feed/').status_code, 200)
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 200)

    def check_pagination(self, paginator, type_text, value):
        """Helper method to validate pagination URLs."""
        for page in range(1, paginator.num_pages + 1):
            context = load_pagination_info(paginator.page(page), type_text, value)
            self.assertIsNotNone(context)
            if context['previous_url']:
                self.assertEqual(self.client.get(context['previous_url']).status_code, 200)
            if context['next_url']:
                self.assertEqual(self.client.get(context['next_url']).status_code, 200)

    def test_image_upload(self):
        """Test image upload and related security validation."""
        img_url = 'https://www.python.org/static/img/python-logo.png'
        img_path = os.path.join(settings.BASE_DIR, 'python.png')

        response = requests.get(img_url)
        with open(img_path, 'wb') as file:
            file.write(response.content)

        self.assertEqual(self.client.post('/upload').status_code, 403)

        sign = get_sha256(get_sha256(settings.SECRET_KEY))
        with open(img_path, 'rb') as file:
            img_file = SimpleUploadedFile('python.png', file.read(), content_type='image/jpg')
            form_data = {'python.png': img_file}
            upload_url = f'/upload?sign={sign}'
            self.assertEqual(self.client.post(upload_url, form_data, follow=True).status_code, 200)

        os.remove(img_path)

        # Avatar and email
        send_email(['qq@qq.com'], 'testTitle', 'testContent')
        save_user_avatar(img_url)

    def test_404_page(self):
        """Test custom 404 error page."""
        self.assertEqual(self.client.get('/nonexistent-url').status_code, 404)

    def test_management_commands(self):
        """Test various custom Django management commands."""
        # OAuth setup
        config = OAuthConfig.objects.create(type='qq', appkey='appkey', appsecret='appsecret')

        OAuthUser.objects.create(
            type='qq',
            openid='openid',
            user=self.user,
            picture=static("/blog/img/avatar.png"),
            metadata='{"figureurl": "https://.../30"}'
        )

        OAuthUser.objects.create(
            type='qq',
            openid='openid1',
            picture='https://.../30',
            metadata='{"figureurl": "https://.../30"}'
        )

        if ELASTICSEARCH_ENABLED:
            call_command("build_index")

        call_command("ping_baidu", "all")
        call_command("create_testdata")
        call_command("clear_cache")
        call_command("sync_user_avatar")
        call_command("build_search_words")
