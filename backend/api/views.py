from io import BytesIO
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.db.models import Case, When, IntegerField
from django.http import HttpResponse
from django_filters.rest_framework.backends import DjangoFilterBackend
from djoser.views import UserViewSet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from rest_framework import filters, status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken, BlacklistedToken
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView

from api.constants import FONT_SIZE, POSITION
from api.filters import RecipeFilter
from api.pagination import CustomPageNumberPagination
from api.permissions import AutorOrReadOnly
from api.serializers import (
    AvatarSerializer,
    IngredientSerializer,
    MyTokenObtainPairSerializer,
    RecipeGetSerializer,
    RecipeSerializer,
    SubscribeSerializer,
    TagSerializer,
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
        context.update(self.kwargs)
        return context

    @action(
        detail=False,
        methods=['put', 'delete'],
        serializer_class=AvatarSerializer,
        url_path='me/avatar'
    )
    def avatar(self, request, *args, **kwargs):
        user = self.get_instance()
        if request.method == "PUT":
            serializer = self.get_serializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == "DELETE":
            user.avatar.delete()
            return Response(status=204)

    @action(
        detail=False,
        methods=['get'],
        serializer_class=SubscribeSerializer,
        pagination_class=CustomPageNumberPagination,
        queryset=Subscribe.objects.all()
    )
    def subscriptions(self, request, *args, **kwargs):
        subscriptions = self.queryset.filter(user=request.user)
        self.queryset = User.objects.filter(
            id__in=subscriptions.values_list('subscribe_id', flat=True))
        recipes_limit = request.GET.get('recipes_limit', 3)
        kwargs['recipes_limit'] = recipes_limit
        return self.list(request, *args, **kwargs)

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=SubscribeSerializer
    )
    def subscribe(self, request, pk=None, *args, **kwargs):

        if request.method == "POST":
            user = request.user
            recipes_limit = request.GET.get('recipes_limit', 3)
            kwargs['recipes_limit'] = recipes_limit
            try:
                sub = self.get_object()
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            if user == sub:
                return Response(
                    {'error': 'You cannot subscribe to yourself'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                subscription = Subscribe.objects.get(user=user, subscribe=sub)
                return Response(
                    {'error': 'You have already subscribed to this author'},
                    status=status.HTTP_400_BAD_REQUEST)
            except Subscribe.DoesNotExist:
                Subscribe.objects.create(user_id=user.id, subscribe_id=sub.id)
            serializer = self.serializer_class(sub, context=kwargs)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == "DELETE":
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
            t, _ = BlacklistedToken.objects.get_or_create(token=token)

        return Response(status=status.HTTP_204_NO_CONTENT)


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    search_fields = ['^name__icontains']
    permission_classes = (permissions.AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    search_fields = ['^name', ]
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        queryset = super().get_queryset()
        search_term = self.request.query_params.get('name')
        if search_term:
            decoded_search_term = unquote(search_term)
            queryset = queryset.annotate(
                starts_with=Case(
                    When(name__istartswith=decoded_search_term, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ).filter(starts_with=1).order_by('-starts_with', 'name')
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = (AutorOrReadOnly,)
    pagination_class = CustomPageNumberPagination
    search_fields = ['name', 'text']
    filterset_class = RecipeFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_permissions(self):
        if self.action in (
            'shopping_cart', 'favorite', 'download_shopping_cart'
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
        if request.method == "POST":
            return self.add_custom(request, model_class)

        elif request.method == "DELETE":
            return self.delete_custom(request, model_class)

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=RecipeGetSerializer
    )
    def favorite(self, request, pk=None):
        model_class = Favorite
        if request.method == "POST":
            return self.add_custom(request, model_class)
        elif request.method == "DELETE":
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

    @action(detail=False, methods=['get'])
    def download_shopping_cart(self, request, *args, **kwargs):
        return DownloadShoppingCart.as_view()(request)


class DownloadShoppingCart(APIView):

    def get(self, request):
        buffer = BytesIO()
        card = ShoppingCart.objects.filter(
            user=self.request.user
        ).prefetch_related(
            'recipe__recipe_ingredients__ingredient'
        )
        ingredients = {}
        for cart in card:
            recipe = cart.recipe
            for ri in recipe.recipe_ingredients.all():
                ingredient = ri.ingredient
                if ingredient.name in ingredients:
                    ingredients[ingredient.name]['amount'] += ri.amount
                else:
                    ingredients[ingredient.name] = {
                        'amount': ri.amount,
                        'measurement_unit': ingredient.measurement_unit
                    }
        print(ingredients)
        pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))

        p = canvas.Canvas(buffer)
        position = POSITION
        p.setFont('Arial', FONT_SIZE)
        p.drawString(POSITION[0], POSITION[1], 'Список покупок:')
        position = (POSITION[0], POSITION[1] - FONT_SIZE)

        for ingredient, data in ingredients.items():
            p.drawString(
                position[0], position[1],
                f'{ingredient} ({data["measurement_unit"]}) — {data["amount"]}'
            )
            position = (position[0], position[1] - FONT_SIZE)
        p.showPage()
        p.save()
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = (
            'attachment;'
            'filename="shopping_cart.pdf"')
        return response
