"""Admin registrations for the boxing app."""

from django.contrib import admin

from boxing.models import Box, Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "length", "width", "height", "weight")
    search_fields = ("name",)


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ("name", "internal_length", "internal_width", "internal_height", "max_weight", "cost")
    search_fields = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at")
    readonly_fields = ("created_at",)
    inlines = [OrderItemInline]
