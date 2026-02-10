# Migration for verification models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('farmers', '0002_farmernote_alter_farmer_options_and_more'),
        ('farms', '0004_remove_farm_boundary_accuracy_meters_and_more'),
        ('accounts', '0003_rename_audit_logs_user_id_e11c73_idx_audit_logs__user_id_7678dc_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GroundTruthReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weather_condition', models.CharField(choices=[('clear', 'Clear/Sunny'), ('cloudy', 'Cloudy'), ('light_rain', 'Light Rain'), ('heavy_rain', 'Heavy Rain'), ('drizzle', 'Drizzle'), ('storm', 'Storm/Thunder'), ('fog', 'Fog'), ('windy', 'Very Windy')], max_length=20)),
                ('temperature_feel', models.CharField(choices=[('very_cold', 'Very Cold'), ('cold', 'Cold'), ('normal', 'Normal'), ('hot', 'Hot'), ('very_hot', 'Very Hot')], max_length=20)),
                ('rainfall_amount', models.CharField(choices=[('none', 'No Rain'), ('light', 'Light (<5mm)'), ('moderate', 'Moderate (5-20mm)'), ('heavy', 'Heavy (>20mm)')], default='none', max_length=20)),
                ('report_time', models.DateTimeField(auto_now_add=True)),
                ('weather_time', models.DateTimeField(help_text='When the weather occurred')),
                ('notes', models.TextField(blank=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='weather_reports/')),
                ('verified', models.BooleanField(default=False)),
                ('farmer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weather_reports', to='farmers.farmer')),
                ('farm', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='farms.farm')),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.user')),
            ],
            options={
                'ordering': ['-report_time'],
            },
        ),
        migrations.CreateModel(
            name='ProofOfAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('fertilizer', 'Applied Fertilizer'), ('pesticide', 'Applied Pesticide'), ('irrigation', 'Irrigated Farm'), ('planting', 'Planted Crops'), ('weeding', 'Weeded Farm'), ('harvesting', 'Harvested Crops'), ('soil_prep', 'Prepared Soil'), ('other', 'Other Action')], max_length=20)),
                ('description', models.TextField()),
                ('action_date', models.DateTimeField()),
                ('photo', models.ImageField(upload_to='proof_of_action/')),
                ('voice_note', models.FileField(blank=True, null=True, upload_to='voice_notes/')),
                ('verified', models.BooleanField(default=False)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('points_earned', models.IntegerField(default=0)),
                ('blockchain_hash', models.CharField(blank=True, help_text='Celo transaction hash', max_length=66)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('farmer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='farmers.farmer')),
                ('farm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='farms.farm')),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.user')),
            ],
            options={
                'ordering': ['-action_date'],
            },
        ),
        migrations.AddIndex(
            model_name='groundtruthreport',
            index=models.Index(fields=['farmer', '-report_time'], name='farmers_gro_farmer_idx'),
        ),
        migrations.AddIndex(
            model_name='groundtruthreport',
            index=models.Index(fields=['weather_time'], name='farmers_gro_weather_idx'),
        ),
        migrations.AddIndex(
            model_name='proofofaction',
            index=models.Index(fields=['farmer', '-action_date'], name='farmers_pro_farmer_idx'),
        ),
        migrations.AddIndex(
            model_name='proofofaction',
            index=models.Index(fields=['verified'], name='farmers_pro_verifie_idx'),
        ),
    ]
