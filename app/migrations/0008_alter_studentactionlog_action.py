# Generated by Django 5.1.4 on 2025-01-09 16:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_studentactionlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentactionlog',
            name='action',
            field=models.CharField(choices=[('page_load', 'Page Loaded'), ('page_unload', 'Page Unloaded'), ('tab_switch', 'Tab Switched'), ('navigation_attempt', 'Navigation Attempt'), ('question_answered', 'Question Answered'), ('inactivity_detected', 'Inactivity Detected'), ('copy_attempt', 'Copy Attempt'), ('screen_resize', 'Screen Resized'), ('network_disconnect', 'Network disconnect'), ('network_reconnect', 'Network reconnect'), ('suspicious_shortcut', 'Suspicious Shortcut Used')], max_length=50),
        ),
    ]
