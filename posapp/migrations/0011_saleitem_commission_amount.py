# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posapp', '0010_add_business_cash_userprofile_logged_sale_merma_product_costo'),
    ]

    operations = [
        migrations.AddField(
            model_name='saleitem',
            name='commission_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cantidad entregada por comisión (cantidad * product.comision)',
                max_digits=10,
                verbose_name='Monto comisión',
            ),
        ),
    ]
