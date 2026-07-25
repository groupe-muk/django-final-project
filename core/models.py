from django.conf import settings
from django.db import models

class Language(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Translation(models.Model):
    INPUT_MODE_CHOICES = [
        ("text", "Text"),
        ("voice", "Voice"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    source_lang = models.ForeignKey(
        Language,
        on_delete=models.RESTRICT,
        related_name="source_translations",
    )
    target_lang = models.ForeignKey(
        Language,
        on_delete=models.RESTRICT,
        related_name="target_translations",
    )

    source_text = models.TextField()
    translated_text = models.TextField()

    was_detected = models.BooleanField(default=False)
    input_mode = models.CharField(
        max_length=16,
        choices=INPUT_MODE_CHOICES,
        default="text",
    )

    latency_ms = models.IntegerField(null=True, blank=True)
    was_successful = models.BooleanField(default=True)
    word_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} ({self.source_lang.code} -> {self.target_lang.code})"

    def save(self, *args, **kwargs):
        self.word_count = len(self.source_text.split()) if self.source_text else 0
        super().save(*args, **kwargs)
