### Описание

Foodgram — проект для публикации рецептов, в котором реализованы следующие возможности, публиковать рецепты, добавлять рецепты в избраное и в корзину покупок, подписываться на авторов, выгружать список ингредиентов для рецептов в корзине.
 
домен foodgram-tasty.duckdns.org
логин foodgram-admin@admin.com
пароль 172835abc_X

### Локальный запуск проекта

Установить [Docker](https://www.docker.com/).
Клонировать репозиторий и перейти в него в командной строке:
```bash
git clone https://github.com/Dardva/foodgram.git
```
```bash
cd foodgram
```
Создать файл окружения .env:
```bash
touch .env
```
Добывить в файл переменные окружения:
```bash
SECRET_KEY 
DEBUG 
ALLOWED_HOSTS
DB_HOST
DB_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
DB_NAME
```
Собрать docker-compose:

```bash
cd ../infra
```
```bash
docker compose up -d
```
Применить миграции в базе данных:
```bash
docker compose exec backend python manage.py migrate
```
Собрать файлы статики:
```bash
docker compose exec backend python manage.py collectstatic
```
```bash
docker compose exec backend cp -r /app/collected_static/. /backend_static/static/
```
Загрузить в базу данных ингредиенты и теги (не обязательно):
```bash
docker compose exec backend python manage.py import_data
```
После запуска проект будут доступен по адресу: http://localhost/

### Примеры запросов и ответов
#### Для неавторизованных пользователей

Для неавторизованных пользователей работа с API доступна в режиме чтения.
```bash
POST api/users/ - регистрация пользователя
GET api/users/{id}/ - получение пользователя по id
GET api/recipes/ - получение списка рецептов
GET api/recipes/{id}/ - получение информации о рецепте
GET api/recipes/{id}/get_link - получение короткой ссылки на рецепт
```

#### Для авторизованных пользователей

- Создание рецепта:
Запрос:
```bash
POST api/recipes/
```
```json
{
  "ingredients": [
    {
      "id": 1123,
      "amount": 10
    }
  ],
  "tags": [
    1,
    2
  ],
  "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAgMAAABieywaAAAACVBMVEUAAAD///9fX1/S0ecCAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAACklEQVQImWNoAAAAggCByxOyYQAAAABJRU5ErkJggg==",
  "name": "string",
  "text": "string",
  "cooking_time": 1
}
```
Ответ при успешноим создании:
```json
{
  "id": 0,
  "tags": [
    {
      "id": 0,
      "name": "Завтрак",
      "slug": "breakfast"
    }
  ],
  "author": {
    "email": "user@example.com",
    "id": 0,
    "username": "string",
    "first_name": "Вася",
    "last_name": "Иванов",
    "is_subscribed": false,
    "avatar": "http://foodgram.example.org/media/users/image.png"
  },
  "ingredients": [
    {
      "id": 0,
      "name": "Картофель отварной",
      "measurement_unit": "г",
      "amount": 1
    }
  ],
  "is_favorited": true,
  "is_in_shopping_cart": true,
  "name": "string",
  "image": "http://foodgram.example.org/media/recipes/images/image.png",
  "text": "string",
  "cooking_time": 1
}
```
- Добавление в список покупок:
Запрос:
```bash
POST api/recipes/{id}/shopping_cart/
```
Ответ:
```json
{
  "id": 0,
  "name": "string",
  "image": "http://foodgram.example.org/media/recipes/images/image.png",
  "cooking_time": 1
}
```
- Добавление аватара:
Запрос:
```bash
POST api/users/me/avatar/
```
Ответ:
```json
{
  "avatar": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAgMAAABieywaAAAACVBMVEUAAAD///9fX1/S0ecCAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAACklEQVQImWNoAAAAggCByxOyYQAAAABJRU5ErkJggg=="
}
```
- Мои подписки
Возвращает пользователей, на которых подписан текущий пользователь. В выдачу добавляются рецепты.
Запрос:
```bash
POST api/users/subscriptions/
```
Ответ:
```json
{
  "count": 123,
  "next": "http://foodgram.example.org/api/users/subscriptions/?page=4",
  "previous": "http://foodgram.example.org/api/users/subscriptions/?page=2",
  "results": [
    {
      "email": "user@example.com",
      "id": 0,
      "username": "string",
      "first_name": "Вася",
      "last_name": "Иванов",
      "is_subscribed": true,
      "recipes": [
        {
          "id": 0,
          "name": "string",
          "image": "http://foodgram.example.org/media/recipes/images/image.png",
          "cooking_time": 1
        }
      ],
      "recipes_count": 0,
      "avatar": "http://foodgram.example.org/media/users/image.png"
    }
  ]
}
```

### Стек технологий
- Python 
- Django 
- Django REST Framework 
- PostgreSQL 
- Nginx 
- gunicorn 
- docker 
- GitHub%20Actions
### Авторы
Малова Дарья
