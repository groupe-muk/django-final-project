from datetime import datetime
from pyexpat import model
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

class Language(models.Model):
    code = models.CharField(max_length=8, null=False, unique=True)  
    name = models.CharField(max_length=64, null=False)               
    is_active = models.BooleanField(default=True, null=False)

    class Meta:
        ordering = ["name"]
        
    def __str__(self):
        return self.name


class Translation(models.Model):

    INPUT_MODE_CHOICES = [
        ("text", "Text"),
        ("voice", "Voice"),
    ]

    user_id = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    source_lang_id = models.ForeignKey(
        Language,
        on_delete=models.RESTRICT,
        related_name="language_source",
    )
    target_lang_id = models.ForeignKey(
        Language,
        on_delete=models.RESTRICT,
        related_name="language_target",
    )

    source_text = models.TextField(null=False)
    translated_text = models.TextField(null=False)

    was_detected = models.BooleanField(default=False,null=False) #True if the source was auto-detected  
    input_mode = models.CharField(
        max_length=16, choices=INPUT_MODE_CHOICES, null=False, default="text"
    )#How the source was entered: 'text' or 'voice'

    latency_ms = models.IntegerField(null=True, blank=True)    
    was_successful = models.BooleanField(default=True, null=False)          
    word_count = models.IntegerField(default=0, null=False)                

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, null=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} ({self.source_lang.code} -> {self.target_lang.code})"

    def save(self, *args, **kwargs):
        if not self.word_count and self.source_text:
            self.word_count = len(self.source_text.split())
        super().save(*args, **kwargs)
