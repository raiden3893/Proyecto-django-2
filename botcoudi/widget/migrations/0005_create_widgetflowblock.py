from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('widget', '0005_widgetconversation_lead_state_lead'),
    ]

    operations = [
        migrations.CreateModel(
            name='WidgetFlowBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nombre del bloque.', max_length=255)),
                ('block_type', models.CharField(choices=[('greeting', 'Saludo inicial'), ('name', 'Nombre'), ('phone', 'Teléfono'), ('email', 'E-mail'), ('insist', 'Insistir'), ('availability', 'Disponibilidad'), ('closing', 'Cierre'), ('custom', 'Mensaje personalizado'), ('contextual', 'Respuesta contextual'), ('menu', 'Menú')], max_length=50)),
                ('order', models.PositiveIntegerField(default=1, help_text='Orden del bloque en el flujo.')),
                ('message', models.TextField(help_text='Mensaje que se mostrará al usuario.')),
                ('required_field', models.CharField(blank=True, help_text='Campo que se espera capturar (nombre, telefono, email, disponibilidad).', max_length=50)),
                ('is_required', models.BooleanField(default=True, help_text='Si este bloque es obligatorio.')),
                ('is_active', models.BooleanField(default=True, help_text='Si este bloque está activo.')),
                ('metadata_json', models.JSONField(blank=True, default=dict, help_text='Metadatos opcionales del bloque.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Bloque de flujo del widget',
                'verbose_name_plural': 'Bloques de flujo del widget',
                'ordering': ('order',),
            },
        ),
    ]