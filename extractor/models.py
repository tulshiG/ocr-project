from django.db import models


class WorkReport(models.Model):
    """One uploaded image = one work report sheet."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    image = models.ImageField(upload_to="work_reports/%Y/%m/%d/")
    location_name = models.CharField(max_length=255, blank=True)  # e.g. "Vadaj", "Paldi", "Memco"
    report_date = models.CharField(max_length=50, blank=True)  # kept as text; source dates are messy (7/6/26, 08-06-2026 etc.)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_model_output = models.TextField(blank=True)  # full raw response, kept for debugging/re-parsing
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.location_name or 'Report'} ({self.report_date or self.uploaded_at.date()}) - {self.status}"


class WorkReportRow(models.Model):
    """One extracted table row."""

    report = models.ForeignKey(WorkReport, related_name="rows", on_delete=models.CASCADE)
    sr = models.CharField(max_length=20, blank=True)
    bus_no = models.CharField(max_length=50, blank=True)   # e.g. TAM17, TCM52, MAC31
    mech = models.CharField(max_length=100, blank=True)    # mechanic name
    work_done = models.TextField(blank=True)
    material = models.CharField(max_length=255, blank=True)  # only some templates have this column
    raw_text = models.TextField(blank=True)  # fallback: whatever couldn't be cleanly split
    row_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["row_order"]

    def __str__(self):
        return f"{self.bus_no}: {self.work_done[:40]}"
