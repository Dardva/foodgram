from django.db.models import Case, IntegerField, Q, When
from django_filters import rest_framework as filters
import unidecode

from recipes.models import Recipe, Ingredient


class RecipeFilter(filters.FilterSet):
    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart')

    class Meta:
        model = Recipe
        fields = ['author', 'tags', 'is_favorited', 'is_in_shopping_cart']

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if user.is_authenticated:
            if value:
                return queryset.filter(favorites__user=user)
            return queryset.exclude(favorites__user=user)
        return queryset.none() if value else queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if user.is_authenticated:
            if value:
                return queryset.filter(shopping_cart__user=user)
            return queryset.exclude(shopping_cart__user=user)
        return queryset.none() if value else queryset


class UnidecodeCharFilter(filters.CharFilter):
    def filter(self, queryset, value):
        value = unidecode.unidecode(value)
        return super().filter(queryset, value)


class IngredientFilter(filters.FilterSet):
    name = UnidecodeCharFilter(
        field_name='name', lookup_expr='istartswith')
    name_contains = UnidecodeCharFilter(
        field_name='name', lookup_expr='icontains')

    class Meta:
        model = Ingredient
        fields = ['name', 'name_contains']

    def filter_queryset(self, queryset):
        search_term = self.form.cleaned_data.get('name')
        if search_term:
            search_term = search_term.casefold()
            queryset = queryset.annotate(
                starts_with=Case(
                    When(name__istartswith=search_term, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ).order_by('-starts_with', 'name')
            return queryset.filter(
                Q(name__istartswith=search_term) | Q(
                    name__icontains=search_term)
            )
        return queryset
