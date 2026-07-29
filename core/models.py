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
        ("document", "Document"),
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

    # Original uploaded filename for document translations (not the extracted text).
    document_name = models.CharField(max_length=255, blank=True, default="")

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

    @property
    def is_document(self) -> bool:
        return self.input_mode == "document"

    @property
    def history_source_label(self) -> str:
        """What history should show instead of dumping extracted document text."""
        if self.is_document:
            return self.document_name or "Uploaded document"
        return self.source_text

    def save(self, *args, **kwargs):
        if self.input_mode == "document":
            if self.document_name and (
                not self.source_text or self.source_text.startswith("[Document]")
            ):
                self.source_text = f"[Document] {self.document_name}"
            if not self.word_count and self.translated_text:
                self.word_count = len(self.translated_text.split())
        else:
            self.word_count = len(self.source_text.split()) if self.source_text else 0
        super().save(*args, **kwargs)
