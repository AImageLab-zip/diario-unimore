from django.conf import settings
from django.db import models


class GoogleCalendarCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='google_credential',
    )
    refresh_token = models.TextField()
    token = models.TextField(blank=True)
    token_uri = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Credenziali Google di {self.user}"


class AcademicActivity(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'In attesa di Esse3'),
        ('SYNCED', 'Sincronizzato su Esse3'),
        ('FAILED', 'Errore sincronizzazione'),
        ('IGNORED', 'Ignorato'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    google_event_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=100, blank=True, null=True)
    sync_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'google_event_id'],
                name='unique_event_per_user',
            )
        ]
        indexes = [models.Index(fields=['user', 'start_time'])]

    def save(self, *args, **kwargs):
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = int(delta.total_seconds() // 60)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.start_time.strftime('%d/%m/%Y %H:%M')})"