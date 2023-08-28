from django.contrib import admin

from apps.blog.models import Category, Image, Post, Tag

admin.site.register(Tag)
admin.site.register(Post)
admin.site.register(Category)
admin.site.register(Image)
