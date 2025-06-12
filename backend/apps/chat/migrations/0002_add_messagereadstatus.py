"""
Migration to add the MessageReadStatus model.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageReadStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company_id', models.IntegerField()),
                ('client_id', models.IntegerField()),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_statuses', db_constraint=False, to='chat.chatmessage')),
            ],
            options={
                'db_table': 'chat_messagereadstatus',
                'unique_together': {('message_id', 'company_id', 'client_id')},
            },
        ),
    ]
