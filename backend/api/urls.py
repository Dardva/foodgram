from django.urls import path
from django.conf.urls import include
from rest_framework import routers

from api.views import (
    IngredientViewSet,
    CustomTokenObtainPairView,
    DownloadShoppingCart,
    RecipeViewSet,
    ResetTokenAPIView,
    TagViewSet,
    UserCustomViewSet
)

router = routers.DefaultRouter()

router.register('users', UserCustomViewSet, basename='users')
router.register('tags', TagViewSet, basename='tags')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet, basename='ingredients')

urlpatterns = [
    path('recipes/download_shopping_cart/',
         DownloadShoppingCart.as_view(), name='download_shopping_cart'),
    path('auth/token/login/',
         CustomTokenObtainPairView.as_view(), name='jwt-create'),
    path('auth/token/logout/',
         ResetTokenAPIView.as_view(), name='token_blacklist'),
    path('', include(router.urls)),
]
