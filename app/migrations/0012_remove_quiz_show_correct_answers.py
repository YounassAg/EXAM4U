# Generated by Django 5.1.4 on 2025-01-15 09:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0011_alter_quiz_options_alter_quizattempt_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quiz',
            name='show_correct_answers',
        ),
    ]
