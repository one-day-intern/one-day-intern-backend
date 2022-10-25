# Generated by Django 4.1.1 on 2022-10-25 17:30

import datetime
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('assessment', '0003_alter_assessmenttool_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestFlow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('test_flow_id', models.UUIDField(auto_created=True, default=uuid.uuid4)),
                ('name', models.CharField(max_length=50)),
                ('is_usable', models.BooleanField(default=False)),
                ('owning_company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='users.company')),
            ],
        ),
        migrations.CreateModel(
            name='TestFlowTool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('release_time', models.TimeField(default=datetime.time(0, 0))),
                ('assessment_tool', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='assessment.assessmenttool')),
                ('test_flow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='assessment.testflow')),
            ],
            options={
                'ordering': ['release_time'],
                'get_latest_by': 'release_time',
            },
        ),
        migrations.AddField(
            model_name='testflow',
            name='tools',
            field=models.ManyToManyField(through='assessment.TestFlowTool', to='assessment.assessmenttool'),
        ),
    ]
