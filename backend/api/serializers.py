import base64

from django.contrib.auth import authenticate, get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserSerializer
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
    Subscribe
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


class UserCustomSerializer(UserSerializer):
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
        user = self.context['request'].user
        if not user.is_authenticated:
            return False
        return user.subscribed.filter(subscribe=obj).exists()


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов рецепта."""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
    )
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit', read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = (
            'id',
            'name',
            'amount',
            'measurement_unit',
        )


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор тегов."""
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор рецептов."""

    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, read_only=True, source='recipe_ingredients')
    author = UserCustomSerializer(read_only=True)
    image = Imagebase64Field()

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

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return user.favorites.filter(recipe=obj).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return user.shopping_cart.filter(recipe=obj).exists()
        return False


class RecipeCreateUpdateSerializer(RecipeSerializer):
    """Сериализатор создания и обновления рецептов."""

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True)
    ingredients = RecipeIngredientSerializer(
        many=True, source='recipe_ingredients')

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

    def validate(self, data):
        super().validate(data)
        if not data.get('recipe_ingredients'):
            raise serializers.ValidationError({
                'ingredients': 'Ingredients are required.'
            })

        ingredient_ids = [ingredient['id'].id
                          for ingredient in data['recipe_ingredients']]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError({
                'ingredients': 'Duplicate ingredients are not allowed.'
            })

        if not data.get('tags'):
            raise serializers.ValidationError({
                'tags': 'Tags are required.'
            })

        tags = data['tags']
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError({
                'tags': 'Duplicate tags are not allowed.'
            })

        return data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        serialize_tags = TagSerializer(instance.tags.all(), many=True).data
        representation['tags'] = serialize_tags
        return representation

    def create_tags(self, tags, recipe):
        try:
            recipe.tags.add(*tags)
        except Tag.DoesNotExist:
            raise serializers.ValidationError(
                'Tag does not exist.')

    def create_ingredients(self, ingredients, recipe):
        current_ingredients = recipe.recipe_ingredients.all()
        ingredients_to_create = []
        for ingredient in ingredients:
            try:
                existing_ingredient = current_ingredients.get(
                    ingredient_id=ingredient['id'].id)
                existing_ingredient.amount = ingredient['amount']
                ingredients_to_create.append(existing_ingredient)
            except RecipeIngredient.DoesNotExist:
                ingredients_to_create.append(RecipeIngredient(
                    recipe=recipe,
                    ingredient_id=ingredient['id'].id,
                    amount=ingredient['amount']
                ))
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(
                    f'Ingredient with ID {ingredient["id"]} does not exist.')
        current_ingredients.delete()
        RecipeIngredient.objects.bulk_create(ingredients_to_create)

    def create(self, validated_data):
        ingredients = validated_data.pop('recipe_ingredients')
        tags = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        Favorite.objects.create(
            user=self.context['request'].user, recipe=recipe)
        ShoppingCart.objects.create(
            user=self.context['request'].user, recipe=recipe
        )
        try:
            self.create_tags(tags, recipe)
            self.create_ingredients(ingredients, recipe)
        except serializers.ValidationError as error:
            recipe.delete()
            raise error
        return recipe

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')
        recipe = super().update(instance, validated_data)
        recipe.tags.clear()
        self.create_tags(tags, recipe)
        self.create_ingredients(ingredients, recipe)
        return instance


class RecipeGetSerializer(serializers.ModelSerializer):
    """Сериализатор списка покупок."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class UserRegisterSerializer(serializers.ModelSerializer):
    """Сериализатор регистрации."""

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
    """Сериализатор аватара."""
    avatar = Imagebase64Field()

    class Meta:
        model = User
        fields = ('avatar',)


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class SubscribeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор подписок."""
    class Meta:
        model = Subscribe
        fields = ('user', 'subscribe')

    def validate(self, data):
        if data['subscribe'] == data['user']:
            raise serializers.ValidationError(
                {'subscribe': 'You cannot subscribe to yourself'}
            )
        if data['user'].subscribed.filter(
            subscribe=data['subscribe']

        ).exists():
            raise serializers.ValidationError(
                {'subscribe': 'You are already subscribed to this author'}
            )
        return data


class SubscribeSerializer(UserCustomSerializer):
    """Сериализатор подписок."""
    recipes = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(read_only=True)

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
            'avatar',
            'recipes_count',
        )
        read_only_fields = ('email', 'id', 'username', 'first_name',
                            'last_name', 'is_subscribed', 'recipes_count',
                            'avatar')

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        recipes_limit = self.context.get('recipes_limit')
        try:
            recipes_limit = int(recipes_limit)
        except ValueError:
            raise serializers.ValidationError(
                {'error': 'Invalid recipes_limit value'}
            )
        recipes = obj.recipes.all()[:recipes_limit]
        return RecipeGetSerializer(recipes, many=True).data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            'password': attrs['password'],
        }
        self.user = authenticate(**authenticate_kwargs)
        if self.user is None or not self.user.is_active:
            raise serializers.ValidationError(
                {'error': 'Invalid credentials'})
        refresh = self.get_token(self.user)
        data = {'auth_token': str(refresh.access_token)}
        return data
