import base64

from django.contrib.auth import authenticate, get_user_model
from django.core.files.base import ContentFile
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Subscribe,
    Tag
)

User = get_user_model()


class Imagebase64Field(serializers.Field):
    def to_internal_value(self, data):
        if not data.startswith('data:image/'):
            raise serializers.ValidationError(
                'Invalid image format.'
            )
        imgstr = data.split(';base64,')[-1]
        ext = data.split(';base64,')[0].split('/')[-1]
        try:
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        except Exception:
            raise serializers.ValidationError(
                'Invalid image format.'
            )
        return data

    def to_representation(self, value):
        if not value:
            return None
        try:
            with open(value.path, 'rb') as image_file:
                data = image_file.read()
            encoded_data = base64.b64encode(data).decode('utf-8')
            ext = value.name.split('.')[-1]
            return f'data:image/{ext};base64,{encoded_data}'
        except Exception:
            return None


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователей."""
    avatar = Imagebase64Field()
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar',
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request', None)
        if request and request.user.is_authenticated:
            user = request.user
            return Subscribe.objects.filter(user=user, subscribe=obj).exists()
        return False


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов рецепта."""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        required=True,
    )
    name = serializers.SerializerMethodField()
    measurement_unit = serializers.SerializerMethodField()

    class Meta:
        model = RecipeIngredient
        fields = (
            'id',
            'name',
            'amount',
            'measurement_unit',
        )
        read_only_fields = ('name', 'measurement_unit')

    def get_name(self, obj):
        return obj.ingredient.name

    def get_measurement_unit(self, obj):
        return obj.ingredient.measurement_unit


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор тегов."""
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор рецептов."""
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Imagebase64Field()
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients', many=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'text',
            'ingredients',
            'author',
            'tags',
            'cooking_time',
            'is_favorited',
            'is_in_shopping_cart',
        )
        read_only_fields = ('id',)

    def get_tags(self, obj):
        tags = obj.tags.all()
        serializer = TagSerializer(tags, many=True)
        return serializer.data

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return Favorite.objects.filter(
                user=self.context['request'].user, recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=self.context['request'].user, recipe=obj
            ).exists()
        return False

    def validate(self, data):
        super().validate(data)
        if data.get('recipe_ingredients'):
            ingredient_ids = [ingredient['id']
                              for ingredient in data['recipe_ingredients']]
            if len(ingredient_ids) == 0:
                raise serializers.ValidationError({
                    'Ingredients are requared'
                })
            elif len(ingredient_ids) != len(set(ingredient_ids)):
                raise serializers.ValidationError({
                    'ingredients': 'Duplicate ingredients are not allowed.'
                })
        else:
            raise serializers.ValidationError({
                'Ingredients are requared'
            })
        try:
            tags = self.context['request'].data['tags']
        except Exception:
            raise serializers.ValidationError({
                'Tags are requared'
            })
        if len(tags) == 0:
            raise serializers.ValidationError({
                'Tags are requared'
            })
        elif len(tags) != len(set(tags)):
            raise serializers.ValidationError({
                'tags': 'Duplicate tags are not allowed.'
            })

        data['tags'] = tags
        return data

    def create(self, validated_data):
        ingredients = validated_data.pop('recipe_ingredients')
        tags = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        Favorite.objects.create(
            user=self.context['request'].user, recipe=recipe)
        ShoppingCart.objects.create(
            user=self.context['request'].user, recipe=recipe
        )
        for tag in tags:
            try:
                tag_instance = Tag.objects.get(id=tag)
                recipe.tags.add(tag_instance)
            except Tag.DoesNotExist:
                recipe.delete()
                raise serializers.ValidationError(
                    f'Tag with ID {tag} does not exist.')
        for ingredient in ingredients:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient['id'].id,
                amount=ingredient['amount'])
        return recipe

    def update(self, instance, validated_data):

        tags = validated_data.pop('tags')

        ingredients = validated_data.pop('recipe_ingredients')

        recipe = super().update(instance, validated_data)
        current_ingredients = recipe.recipe_ingredients.all()
        recipe.tags.clear()
        for tag in tags:
            try:
                tag_instance = Tag.objects.get(id=tag)
                recipe.tags.add(tag_instance)
            except Tag.DoesNotExist:
                raise serializers.ValidationError(
                    f'Tag with ID {tag} does not exist.')

        for ingredient in ingredients:
            try:
                recipe_ingredient, created = (
                    RecipeIngredient.objects.get_or_create(
                        recipe=recipe,
                        ingredient_id=ingredient['id'].id,
                        defaults={'amount': ingredient['amount']}
                    ))
                if not created:
                    recipe_ingredient.amount = ingredient['amount']
                    recipe_ingredient.save()
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(
                    f'Ingredient with ID {ingredient["id"]}'
                    'does not exist.')
            for current_ingredient in current_ingredients.exclude(
                id__in=[i['id'].id for i in ingredients]
            ):
                current_ingredient.delete()
        return instance


class RecipeGetSerializer(serializers.ModelSerializer):
    """Сериализатор списка покупок."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class UserRegisterSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
        )


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Imagebase64Field()

    class Meta:
        model = User
        fields = ('avatar',)


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class SubscribeSerializer(serializers.ModelSerializer):
    """Сериализатор подписок."""
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
            'avatar',
        )

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        recipes_limit = self.context.get('recipes_limit')
        if recipes_limit is not None:
            try:
                recipes_limit = int(recipes_limit)
            except ValueError:
                return Response(
                    {'error': 'Invalid recipes_limit value'},
                    status=status.HTTP_400_BAD_REQUEST)
        if recipes_limit is None:
            return RecipeGetSerializer(
                Recipe.objects.filter(author=obj), many=True
            ).data
        recipes = Recipe.objects.filter(
            author=obj)[:recipes_limit]
        return RecipeGetSerializer(recipes, many=True).data

    def get_recipes_count(self, obj):
        return Recipe.objects.filter(author=obj).count()


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': attrs['password'],
        }
        self.user = authenticate(**authenticate_kwargs)
        if self.user is None or not self.user.is_active:
            raise serializers.ValidationError(
                {'error': 'Invalid credentials'}, code=400)
        refresh = self.get_token(self.user)
        data = {'auth_token': str(refresh.access_token)}
        return data
