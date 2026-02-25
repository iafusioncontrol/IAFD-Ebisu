# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('posapp', '0002_rename_products_business_updated_idx_products_busines_756c1b_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Usuario que realizó la venta',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales_created',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Creado por',
            ),
        ),
    ]
