import os
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db.models import (
    BooleanField, Case, Count, F, Sum, When
)
from django.http import HttpResponse
from django_filters.rest_framework.backends import DjangoFilterBackend
from djoser.views import UserViewSet

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from rest_framework import (
    filters, status, permissions, viewsets
)
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken, BlacklistedToken
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView

from api.constants import (
    FONT_SIZE, POSITION, RECIPES_LIMIT
)
from api.filters import (
    RecipeFilter, IngredientFilter
)
from api.pagination import CustomPageNumberPagination
from api.permissions import AutorOrReadOnly
from api.serializers import (
    AvatarSerializer, IngredientSerializer,
    CustomTokenObtainPairSerializer, RecipeGetSerializer,
    RecipeCreateUpdateSerializer, RecipeSerializer,
    SubscribeSerializer, TagSerializer, SubscribeCreateSerializer
)
from recipes.models import (
    Favorite, Ingredient, Recipe, ShoppingCart, Subscribe, Tag
)

User = get_user_model()


class UserCustomViewSet(UserViewSet):
    pagination_class = CustomPageNumberPagination

    def get_permissions(self):
        if self.action in ('avatar', 'subscriptions', 'me', 'subscribe'):
            self.permission_classes = (permissions.IsAuthenticated,)
        return super().get_permissions()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'subscriptions':
            context['recipes_limit'] = self.request.GET.get(
                'recipes_limit', RECIPES_LIMIT)

        return context

    @action(
        detail=False,
        methods=['put', 'delete'],
        serializer_class=AvatarSerializer,
        url_path='me/avatar'
    )
    def avatar(self, request, *args, **kwargs):
        user = self.get_instance()
        if request.method == 'PUT':
            serializer = self.get_serializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            user.avatar.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        serializer_class=SubscribeSerializer,
        pagination_class=CustomPageNumberPagination
    )
    def subscriptions(self, request, *args, **kwargs):
        self.queryset = User.objects.annotate(
            is_subscribe=Case(
                When(subscribe__user=request.user, then=True),
                default=False,
                output_field=BooleanField()
            ),
            recipes_count=Count('recipes')
        ).filter(is_subscribe=True)

        return self.list(request, *args, **kwargs)

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=SubscribeCreateSerializer
    )
    def subscribe(self, request, pk=None, *args, **kwargs):

        if request.method == 'POST':
            user = request.user
            try:
                recipes_limit = int(request.GET.get(
                    'recipes_limit', RECIPES_LIMIT))
            except ValueError:
                raise ValueError(
                    f'{self.request}, Invalid recipes_limit value')
            kwargs['recipes_limit'] = recipes_limit
            try:
                sub = self.get_queryset().annotate(
                    recipes_count=Count('recipes')
                ).get(id=self.get_object().id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            create_serializer = self.get_serializer(
                data={
                    'user': request.user.id,
                    'subscribe': self.get_object().id})
            create_serializer.is_valid(raise_exception=True)
            create_serializer.save(user=user)
            serializer = SubscribeSerializer(sub, context=kwargs)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == 'DELETE':
            user = request.user
            try:
                sub = self.get_object()
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            try:
                subscription = Subscribe.objects.get(user=user, subscribe=sub)
            except Subscribe.DoesNotExist:
                return Response(
                    {'error': 'You are not subscribed to this author'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class ResetTokenAPIView(APIView):
    """
    Добавляет все refresh токены пользователя в черный список
    """

    def post(self, request: Request) -> Response:
        tokens = OutstandingToken.objects.filter(user_id=request.user.id)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = [DjangoFilterBackend]
    permission_classes = (permissions.AllowAny,)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().select_related(
        'author').prefetch_related('ingredients', 'tags')
    permission_classes = (AutorOrReadOnly,)
    pagination_class = CustomPageNumberPagination
    search_fields = ['name', 'text']
    filterset_class = RecipeFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_permissions(self):
        if self.action in (
            'shopping_cart', 'favorite'
        ):
            self.permission_classes = (permissions.IsAuthenticated,)
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        link = recipe.get_link()
        return Response({'short-link': link}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=RecipeGetSerializer
    )
    def shopping_cart(self, request, pk=None):
        model_class = ShoppingCart
        if request.method == 'POST':
            return self.add_custom(request, model_class)

        if request.method == 'DELETE':
            return self.delete_custom(request, model_class)

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=RecipeGetSerializer
    )
    def favorite(self, request, pk=None):
        model_class = Favorite
        if request.method == 'POST':
            return self.add_custom(request, model_class)
        if request.method == 'DELETE':
            return self.delete_custom(request, model_class)

    def add_custom(self, request, model_class, *args, **kwargs):
        user = request.user
        recipe = self.get_object()
        if model_class.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                {'error':
                    'You already have this recipe in your shopping cart'},
                status=status.HTTP_400_BAD_REQUEST
            )
        model_class.objects.create(user=user, recipe=recipe)
        serializer = self.serializer_class(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_custom(self, request, model_class, *args, **kwargs):
        user = request.user
        recipe = self.get_object()
        try:
            obj = model_class.objects.get(user=user, recipe=recipe)
        except model_class.DoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DownloadShoppingCart(APIView):

    def get(self, request):
        ingredients = ShoppingCart.objects.select_related(
            'recipe', 'recipe__recipe_ingredients'
        ).prefetch_related(
            'recipe__recipe_ingredients__ingredient'
        ).filter(
            user=self.request.user
        ).values(
            name=F('recipe__recipe_ingredients__ingredient__name'),
            unit=F('recipe__recipe_ingredients__ingredient__measurement_unit'),
        ).annotate(
            amount=Sum('recipe__recipe_ingredients__amount')
        ).values(
            'name', 'unit', 'amount'
        ).order_by('name')

        buffer = self.get_file(ingredients)
        response = HttpResponse(
            buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = (
            'attachment;'
            'filename="shopping_cart.pdf"')
        return response

    def get_file(self, ingredients):
        buffer = BytesIO()
        font_path = os.path.join(os.path.dirname(
            __file__), '../ttf/DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        p = canvas.Canvas(buffer)
        left, top = POSITION
        p.setFont('DejaVuSans', FONT_SIZE)
        p.drawString(left, top, 'Список покупок:')
        top -= FONT_SIZE

        for ingredient in ingredients:
            name = ingredient['name']
            unit = ingredient['unit']
            amount = ingredient['amount']
            p.drawString(
                left, top,
                f'{name} ({unit}) — {amount}'
            )
            top -= FONT_SIZE
        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer
