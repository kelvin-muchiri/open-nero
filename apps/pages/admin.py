from django.contrib import admin

from .models import Image, NavbarLink, Page

admin.site.register(Page)
admin.site.register(NavbarLink)
admin.site.register(Image)
