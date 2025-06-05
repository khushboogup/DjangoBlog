import logging
import os
import uuid
from blog.forms import ArticleForm
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from haystack.views import SearchView
from django.shortcuts import render, redirect
from blog.models import Article, Category, LinkShowType, Links, Tag
from comments.forms import CommentForm
from djangoblog.utils import cache, get_blog_setting, get_sha256
from django.contrib.auth.decorators import login_required
from django.contrib import messages

logger = logging.getLogger(__name__)




# views.py
@login_required
def ai_generate_article(request):
    """View to handle AI-generated article creation with preview option."""
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        action = request.POST.get('action')  # 'preview' or 'save'

        logger.debug(f"Form submitted with action: {action}, data: {request.POST}")

        if form.is_valid():
            try:
                article = form.save(commit=False)
                prompt = form.cleaned_data.get('prompt')

                if not prompt:
                    messages.error(request, _('Please provide a prompt for AI generation.'))
                    logger.warning("No prompt provided in AI article generation.")
                    return render(request, 'blog/ai_generate_article.html', {'form': form})

                logger.debug(f"Generating content for prompt: {prompt}")
                content = article.generate_content(prompt)
                if not content:
                    messages.error(request, _('Failed to generate article content. Please try again.'))
                    logger.error("Failed to generate article content for prompt: %s", prompt)
                    return render(request, 'blog/ai_generate_article.html', {'form': form})

                if action == 'preview':
                    logger.info(f"Previewing article with title: {form.cleaned_data.get('title')}")
                    return render(request, 'blog/ai_generate_article.html', {
                        'form': form,
                        'preview_content': content,
                        'preview_title': form.cleaned_data.get('title')
                    })

                article.body = content
                article.author = request.user
                # Set default category if not provided
                if not article.category:
                    article.category = Category.objects.first() or Category.objects.create(name="General", slug="general")
                article.save()
                form.save_m2m()  # Save many-to-many fields (e.g., tags)
                cache.clear()
                logger.info(f"AI-generated article created: {article.title} (ID: {article.id})")
                messages.success(request, _('Article successfully generated and saved!'))
                return redirect(article.get_absolute_url())

            except Exception as e:
                logger.error(f"Error in AI article generation: {e}", exc_info=True)
                messages.error(request, _('An error occurred while generating the article: ') + str(e))
        else:
            logger.warning(f"Form validation failed: {form.errors}")
            messages.error(request, _('Please correct the form errors: ') + str(form.errors))
    else:
        form = ArticleForm()

    return render(request, 'blog/ai_generate_article.html', {'form': form})


class ArticleListView(ListView):
    # template_name specifies which template to use for rendering
    template_name = 'blog/article_index.html'
    context_object_name = 'article_list'
    page_type = ''
    paginate_by = settings.PAGINATE_BY
    page_kwarg = 'page'
    link_type = LinkShowType.L

    def get_view_cache_key(self):
        return self.request.GET.get(self.page_kwarg, '1')  # Fixed: Use GET and page_kwarg

    @property
    def page_number(self):
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or '1'
        try:
            return int(page)
        except ValueError:
            return 1

    def get_queryset_cache_key(self):
        """
        Subclasses should override this to generate cache key for queryset.
        """
        raise NotImplementedError()

    def get_queryset_data(self):
        """
        Subclasses should override this to fetch the queryset data.
        """
        raise NotImplementedError()

    def get_queryset_from_cache(self, cache_key):
        """
        Cache page data
        :param cache_key: cache key
        :return:
        """
        value = cache.get(cache_key)
        if value:
            logger.info('get view cache.key:{key}'.format(key=cache_key))
            return value
        else:
            article_list = self.get_queryset_data()
            cache.set(cache_key, article_list)
            logger.info('set view cache.key:{key}'.format(key=cache_key))
            return article_list

    def get_queryset(self):
        """
        Override default method to get data from cache
        :return:
        """
        key = self.get_queryset_cache_key()
        value = self.get_queryset_from_cache(key)
        return value

    def get_context_data(self, **kwargs):
        kwargs['linktype'] = self.link_type
        return super(ArticleListView, self).get_context_data(**kwargs)
   
class IndexView(ArticleListView):
    """
    Homepage
    """
    # Friend link type
    link_type = LinkShowType.I

    def get_queryset_data(self):
        article_list = Article.objects.filter(type='a', status='p')
        return article_list

    def get_queryset_cache_key(self):
        cache_key = 'index_{page}'.format(page=self.page_number)
        return cache_key


class ArticleDetailView(DetailView):
    """
    Article detail page
    """
    template_name = 'blog/article_detail.html'
    model = Article
    pk_url_kwarg = 'article_id'
    context_object_name = "article"

    def get_object(self, queryset=None):
        obj = super(ArticleDetailView, self).get_object()
        obj.viewed()
        self.object = obj
        return obj

    def get_context_data(self, **kwargs):
        comment_form = CommentForm()
        article_comments = self.object.comment_list()
        parent_comments = article_comments.filter(parent_comment=None)
        blog_setting = get_blog_setting()
        paginator = Paginator(parent_comments, blog_setting.article_comment_count)
        page = self.request.GET.get('comment_page', '1')
        if not page.isnumeric():
            page = 1
        else:
            page = int(page)
            if page < 1:
                page = 1
            if page > paginator.num_pages:
                page = paginator.num_pages

        p_comments = paginator.page(page)
        next_page = p_comments.next_page_number() if p_comments.has_next() else None
        prev_page = p_comments.previous_page_number() if p_comments.has_previous() else None

        if next_page:
            kwargs['comment_next_page_url'] = self.object.get_absolute_url() + f'?comment_page={next_page}#commentlist-container'
        if prev_page:
            kwargs['comment_prev_page_url'] = self.object.get_absolute_url() + f'?comment_page={prev_page}#commentlist-container'
        kwargs['form'] = comment_form
        kwargs['article_comments'] = article_comments
        kwargs['p_comments'] = p_comments
        kwargs['comment_count'] = len(article_comments) if article_comments else 0
        kwargs['next_article'] = self.object.next_article
        kwargs['prev_article'] = self.object.prev_article

        return super(ArticleDetailView, self).get_context_data(**kwargs)


class CategoryDetailView(ArticleListView):
    """
    Category list
    """
    page_type = "Category Archive"

    def get_queryset_data(self):
        slug = self.kwargs['category_name']
        category = get_object_or_404(Category, slug=slug)
        categoryname = category.name
        self.categoryname = categoryname
        categorynames = list(map(lambda c: c.name, category.get_sub_categorys()))
        article_list = Article.objects.filter(category__name__in=categorynames, status='p')
        return article_list

    def get_queryset_cache_key(self):
        slug = self.kwargs['category_name']
        category = get_object_or_404(Category, slug=slug)
        categoryname = category.name
        self.categoryname = categoryname
        cache_key = 'category_list_{categoryname}_{page}'.format(categoryname=categoryname, page=self.page_number)
        return cache_key

    def get_context_data(self, **kwargs):
        categoryname = self.categoryname
        try:
            categoryname = categoryname.split('/')[-1]
        except BaseException:
            pass
        kwargs['page_type'] = CategoryDetailView.page_type
        kwargs['tag_name'] = categoryname
        return super(CategoryDetailView, self).get_context_data(**kwargs)


class AuthorDetailView(ArticleListView):
    """
    Author's articles
    """
    page_type = 'Author Article Archive'

    def get_queryset_cache_key(self):
        from uuslug import slugify
        author_name = slugify(self.kwargs['author_name'])
        cache_key = 'author_{author_name}_{page}'.format(author_name=author_name, page=self.page_number)
        return cache_key

    def get_queryset_data(self):
        author_name = self.kwargs['author_name']
        article_list = Article.objects.filter(author__username=author_name, type='a', status='p')
        return article_list

    def get_context_data(self, **kwargs):
        author_name = self.kwargs['author_name']
        kwargs['page_type'] = AuthorDetailView.page_type
        kwargs['tag_name'] = author_name
        return super(AuthorDetailView, self).get_context_data(**kwargs)


class TagDetailView(ArticleListView):
    """
    Tag archive page
    """
    page_type = 'Tag Archive'

    def get_queryset_data(self):
        slug = self.kwargs['tag_name']
        tag = get_object_or_404(Tag, slug=slug)
        tag_name = tag.name
        self.name = tag_name
        article_list = Article.objects.filter(tags__name=tag_name, type='a', status='p')
        return article_list

    def get_queryset_cache_key(self):
        slug = self.kwargs['tag_name']
        tag = get_object_or_404(Tag, slug=slug)
        tag_name = tag.name
        self.name = tag_name
        cache_key = 'tag_{tag_name}_{page}'.format(tag_name=tag_name, page=self.page_number)
        return cache_key

    def get_context_data(self, **kwargs):
        tag_name = self.name
        kwargs['page_type'] = TagDetailView.page_type
        kwargs['tag_name'] = tag_name
        return super(TagDetailView, self).get_context_data(**kwargs)


class ArchivesView(ArticleListView):
    """
    Article archive page
    """
    page_type = 'Article Archive'
    paginate_by = None
    page_kwarg = None
    template_name = 'blog/article_archives.html'

    def get_queryset_data(self):
        return Article.objects.filter(status='p').all()

    def get_queryset_cache_key(self):
        cache_key = 'archives'
        return cache_key


class LinkListView(ListView):
    model = Links
    template_name = 'blog/links_list.html'

    def get_queryset(self):
        return Links.objects.filter(is_enable=True)


class EsSearchView(SearchView):
    def get_context(self):
        paginator, page = self.build_page()
        context = {
            "query": self.query,
            "form": self.form,
            "page": page,
            "paginator": paginator,
            "suggestion": None,
        }
        if hasattr(self.results, "query") and self.results.query.backend.include_spelling:
            context["suggestion"] = self.results.query.get_spelling_suggestion()
        context.update(self.extra_context())
        return context


@csrf_exempt
def fileupload(request):
    """
    This method needs a custom client to upload files. It only provides image hosting functionality.
    :param request:
    :return:
    """
    if request.method == 'POST':
        sign = request.GET.get('sign', None)
        if not sign:
            return HttpResponseForbidden()
        if not sign == get_sha256(get_sha256(settings.SECRET_KEY)):
            return HttpResponseForbidden()
        response = []
        for filename in request.FILES:
            timestr = timezone.now().strftime('%Y/%m/%d')
            imgextensions = ['jpg', 'png', 'jpeg', 'bmp']
            fname = u''.join(str(filename))
            isimage = len([i for i in imgextensions if fname.find(i) >= 0]) > 0
            base_dir = os.path.join(settings.STATICFILES, "files" if not isimage else "image", timestr)
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            savepath = os.path.normpath(os.path.join(base_dir, f"{uuid.uuid4().hex}{os.path.splitext(filename)[-1]}"))
            if not savepath.startswith(base_dir):
                return HttpResponse("only for post")
            with open(savepath, 'wb+') as wfile:
                for chunk in request.FILES[filename].chunks():
                    wfile.write(chunk)
            if isimage:
                from PIL import Image
                image = Image.open(savepath)
                image.save(savepath, quality=20, optimize=True)
            url = static(savepath)
            response.append(url)
        return HttpResponse(response)
    else:
        return HttpResponse("only for post")


def page_not_found_view(request, exception, template_name='blog/error_page.html'):
    if exception:
        logger.error(exception)
    url = request.get_full_path()
    return render(request,
                  template_name,
                  {'message': _('Sorry, the page you requested is not found, please click the home page to see other?'),
                   'statuscode': '404'},
                  status=404)


def server_error_view(request, template_name='blog/error_page.html'):
    return render(request,
                  template_name,
                  {'message': _('Sorry, the server is busy, please click the home page to see other?'),
                   'statuscode': '500'},
                  status=500)


def permission_denied_view(request, exception, template_name='blog/error_page.html'):
    if exception:
        logger.error(exception)
    return render(request,
                  template_name,
                  {'message': _('Sorry, you do not have permission to access this page?'),
                   'statuscode': '403'},
                  status=403)


def clean_cache_view(request):
    cache.clear()
    return HttpResponse('ok')
