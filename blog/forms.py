import logging
from .models import Article
from django import forms
from haystack.forms import SearchForm
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class BlogSearchForm(SearchForm):
    querydata = forms.CharField(required=True)

    def search(self):
        datas = super(BlogSearchForm, self).search()
        if not self.is_valid():
            return self.no_query_found()

        if self.cleaned_data['querydata']:
            logger.info(self.cleaned_data['querydata'])
        return datas
class ArticleForm(forms.ModelForm):
    prompt = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Enter a prompt for AI to generate the article content (e.g., "Write a blog post about sustainable living").'
        })
    )

    class Meta:
        model = Article
        fields = ['title', 'prompt', 'category', 'tags', 'status', 'comment_status', 'type', 'article_order', 'show_toc']

    def clean(self):
        cleaned_data = super().clean()
        prompt = cleaned_data.get('prompt')
        title = cleaned_data.get('title')

        if prompt and not title:
            raise forms.ValidationError(_('Please provide a title when using an AI prompt.'))
        return cleaned_data
