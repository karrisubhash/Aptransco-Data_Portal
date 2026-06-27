from django.db import models


class TransmissionLine(models.Model):
    line_name = models.CharField(max_length=300, unique=True)
    voltage = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["line_name"]
        verbose_name = "Transmission Line"
        verbose_name_plural = "Transmission Lines"

    def __str__(self):
        return self.line_name