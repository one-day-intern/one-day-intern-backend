from django.db import models


class AssessmentEvent(models.Model):
    """
    Dummy Model for Initial Check
    """
    assessment_name = models.CharField(max_length=40)
