from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Subscribe,
    Tag,
)

User = get_user_model()


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 3
    fields = ('ingredient', 'amount')


class FavoriteInline(admin.TabularInline):
    model = Favorite
    list_display = ('recipe',)


class ShoppingCartInline(admin.TabularInline):
    model = ShoppingCart
    list_display = ('recipe',)


class SubscribeInline(admin.TabularInline):
    model = Subscribe
    fk_name = 'user'
    list_display = ('subscribe',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit')
    search_fields = ('name', )


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'author')
    fields = ('author', 'name', 'image', 'text', 'cooking_time',
              'tags', 'favorite_count')
    search_fields = ('author', 'name')
    list_filter = ('tags',)
    readonly_fields = ('favorite_count',)
    inlines = [RecipeIngredientInline, ]

    def favorite_count(self, obj):
        count = Favorite.objects.filter(recipe=obj).count()

        return 'у {} пользователей'.format(count)

    favorite_count.short_description = 'В избранном'


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name')
    search_fields = ('username', 'email')
    inlines = [FavoriteInline, ShoppingCartInline, SubscribeInline]


admin.site.register(User, UserAdmin)
