# Generated by Django 5.1.4 on 2025-01-15 08:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_alter_studentactionlog_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_published', models.BooleanField(default=False)),
                ('time_limit', models.IntegerField(blank=True, help_text='Time limit in minutes', null=True)),
                ('passing_score', models.FloatField(default=60.0, help_text='Minimum score required to pass the quiz (percentage)')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.course')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 'teacher'}, on_delete=django.db.models.deletion.CASCADE, to='app.userprofile')),
            ],
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('score', models.FloatField(blank=True, null=True)),
                ('is_completed', models.BooleanField(default=False)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.quiz')),
                ('student', models.ForeignKey(limit_choices_to={'role': 'student'}, on_delete=django.db.models.deletion.CASCADE, to='app.userprofile')),
            ],
        ),
        migrations.CreateModel(
            name='QuizQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField()),
                ('points', models.FloatField(default=1.0)),
                ('explanation', models.TextField(blank=True, help_text='Explanation shown after answering', null=True)),
                ('order', models.IntegerField(default=0)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='app.quiz')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='QuizChoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice_text', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField(default=False)),
                ('explanation', models.TextField(blank=True, help_text='Explanation for this choice', null=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='app.quizquestion')),
            ],
        ),
        migrations.CreateModel(
            name='QuizResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_correct', models.BooleanField(default=False)),
                ('points_earned', models.FloatField(default=0.0)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='app.quizattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.quizquestion')),
                ('selected_choices', models.ManyToManyField(to='app.quizchoice')),
            ],
        ),
    ]
