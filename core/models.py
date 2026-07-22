from django.db import models


# Create your models here.
class Language(models.Model):
    code = models.CharField(max_length=8, null=False, unique=True)
    name = models.CharField(max_length=64, null=False)
    is_active = models.BooleanField(default=True, null=False)
