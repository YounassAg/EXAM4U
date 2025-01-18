# Generated by Django 5.1.5 on 2025-01-18 17:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_remove_group_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='end_year',
            field=models.IntegerField(default=2024),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='group',
            name='start_year',
            field=models.IntegerField(default=2024),
            preserve_default=False,
        ),
    ]
