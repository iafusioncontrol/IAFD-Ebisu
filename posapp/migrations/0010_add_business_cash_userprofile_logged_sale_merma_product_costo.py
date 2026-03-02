# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posapp', '0009_alter_product_unique_together_product_local_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='cash_on_hand',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cantidad de dinero en caja. Solo el administrador puede editarlo.',
                max_digits=12,
                verbose_name='Dinero en caja',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='logged',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='True si el usuario está autenticado en algún dispositivo.',
                verbose_name='Sesión activa',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='merma',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='True si es una venta de merma (total=0, baja de stock sin ingreso)',
                verbose_name='Merma',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='causa_merma',
            field=models.CharField(
                blank=True,
                help_text='Descripción de la causa de la merma',
                max_length=255,
                null=True,
                verbose_name='Causa de la merma',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='costo',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                help_text='Costo del producto',
                max_digits=10,
                verbose_name='Costo',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='ganancia',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                help_text='Ganancia del producto',
                max_digits=10,
                verbose_name='Ganancia',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='comision',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                help_text='Comisión del producto',
                max_digits=10,
                verbose_name='Comisión',
            ),
        ),
    ]
