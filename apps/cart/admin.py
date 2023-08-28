from django.contrib import admin

from apps.cart.models import Attachment, Cart, Item


class AttachmentInline(admin.StackedInline):
    model = Attachment
    extra = 0


class ItemInline(admin.StackedInline):
    model = Item
    extra = 0


class CartAdmin(admin.ModelAdmin):
    list_display = ("owner",)
    search_fields = ("owner",)
    inlines = (ItemInline,)


class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "topic",
        "cart",
    )
    search_fields = ("cart__owner", "topic")
    inlines = (AttachmentInline,)


admin.site.register(Cart, CartAdmin)
admin.site.register(Item, ItemAdmin)
