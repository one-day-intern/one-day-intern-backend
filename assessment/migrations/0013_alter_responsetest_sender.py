# Generated by Django 4.1.1 on 2022-11-21 16:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0012_alter_testflowtool_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="responsetest", name="sender", field=models.TextField(),
        ),
    ]
