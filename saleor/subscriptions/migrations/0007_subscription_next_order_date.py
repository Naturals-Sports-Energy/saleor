# Generated by Django 3.1.2 on 2021-05-19 17:30

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0006_subscription_token_customer_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='next_order_date',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
