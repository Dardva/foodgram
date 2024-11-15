import csv
import os
import pathlib

from django.core.management.base import BaseCommand

from recipes.models import (
    Ingredient,
    Tag,
)


class Command(BaseCommand):
    """
    Класс для импорта данных из csv файлов в базу данных.
    """

    def handle(self, *args, **options):

        self.load_data()

    def load_data(self):
        """
        Считывает данные из csv файлов и сохраняет их в базу данных.
        """
        root_dir = pathlib.Path(__file__).parent.parent.parent.parent
        data_dir = root_dir / 'data'

        models = {
            'ingredients.csv': Ingredient,
            'tags.csv': Tag,
        }
        for filename, model in models.items():
            file_path = os.path.join(data_dir, filename)

            with open(file_path, encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)

                for row in reader:
                    model.objects.get_or_create(**row)
            self.stdout.write(
                self.style.SUCCESS(
                    'Successfully imported data from %s' % filename)
            )
        self.stdout.write(
            self.style.SUCCESS('Imported all data')
        )
