# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posapp', '0003_sale_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='pending_approval',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='True si fue enviada por trabajador y admin aún no la aprobó',
                verbose_name='Pendiente de aprobación',
            ),
        ),
    ]
