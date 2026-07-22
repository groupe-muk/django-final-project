from datetime import datetime
from pyexpat import model

from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Language(models.Model):
    code = models.CharField(max_length=8, null=False, unique=True)
    name = models.CharField(max_length=64, null=False)
    is_active = models.BooleanField(default=True, null=False)

class Translation(models.Model):
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name="translations")
    source_lang_id = models.ForeignKey(Language, on_delete=models.RESTRICT, related_name="language_source")
    target_lang_id = models.ForeignKey(Language, on_delete=models.RESTRICT, related_name="language_target")
    source_text = models.TextField(null= False)
    translated_text = models.TextField(null= False)
    was_detected = models.BooleanField(null= False, default= False) #True if the source was auto-detected
    input_mode = models.CharField(max_length=16, null= False, default="text") #How the source was entered: 'text' or 'voice'
    was_successful = models.BooleanField(null= False, default=True)
    latency_ms = models.IntegerField()
    word_count = models.IntegerField(default=0, null=False)
    created_at = models.DateTimeField(null=False, default=datetime.now())
    


