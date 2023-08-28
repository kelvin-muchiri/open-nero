from django.contrib import admin

from .models import Payment, Paypal, Subscription

admin.site.register(Subscription)
admin.site.register(Paypal)
admin.site.register(Payment)
