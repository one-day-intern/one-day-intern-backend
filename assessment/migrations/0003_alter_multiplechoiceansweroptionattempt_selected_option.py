# Generated by Django 4.1.1 on 2022-12-11 15:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0002_interactivequizattempt_submitted_time_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="multiplechoiceansweroptionattempt",
            name="selected_option",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="selected_option",
                to="assessment.multiplechoiceansweroption",
            ),
        ),
    ]