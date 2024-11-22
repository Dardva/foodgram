from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import NAME_LENGTH, EMAIL_LENGTH


class User(AbstractUser):
    """Модель пользователя."""
    email = models.EmailField('Email', unique=True, max_length=EMAIL_LENGTH)
    first_name = models.CharField('Имя', max_length=NAME_LENGTH)
    last_name = models.CharField('Фамилия', max_length=NAME_LENGTH)
    avatar = models.ImageField(
        upload_to='users/images/',
        null=True,
        default=None,
        verbose_name='Аватар',
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'id',
        'username',
        'first_name',
        'last_name',
    ]

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username', 'id',)

    def __str__(self):
        return self.username
