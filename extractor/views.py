from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import WorkReportUploadForm
from .models import WorkReport, WorkReportRow
from .services import OCRExtractionError, extract_structured_data


def upload_view(request):
    if request.method == "POST":
        form = WorkReportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save()
            return redirect("extractor:process", pk=report.pk)
    else:
        form = WorkReportUploadForm()

    reports = WorkReport.objects.order_by("-uploaded_at")[:20]
    return render(request, "extractor/upload.html", {"form": form, "reports": reports})


def process_view(request, pk):
    """Runs extraction synchronously and redirects to the result. Kept simple on purpose —
    swap this for a Celery task (see README) once you have more than a couple of users."""
    report = get_object_or_404(WorkReport, pk=pk)

    report.status = WorkReport.STATUS_PROCESSING
    report.save(update_fields=["status"])

    try:
        result = extract_structured_data(report.image.path)
    except OCRExtractionError as e:
        report.status = WorkReport.STATUS_FAILED
        report.error_message = str(e)
        report.save(update_fields=["status", "error_message"])
        messages.error(request, f"Extraction failed: {e}")
        return redirect("extractor:upload")

    report.location_name = result["location_name"]
    report.report_date = result["report_date"]
    report.raw_model_output = result["raw_output"]
    report.status = WorkReport.STATUS_DONE
    report.processed_at = timezone.now()
    report.save()

    # Clear any previous rows (in case of re-processing) then bulk create
    report.rows.all().delete()
    WorkReportRow.objects.bulk_create(
        [
            WorkReportRow(
                report=report,
                sr=row["sr"],
                bus_no=row["bus_no"],
                mech=row["mech"],
                work_done=row["work_done"],
                material=row["material"],
                row_order=i,
            )
            for i, row in enumerate(result["rows"])
        ]
    )

    messages.success(request, f"Extracted {len(result['rows'])} rows.")
    return redirect("extractor:detail", pk=report.pk)


def detail_view(request, pk):
    report = get_object_or_404(WorkReport, pk=pk)
    return render(request, "extractor/detail.html", {"report": report})


def reprocess_view(request, pk):
    """Manual re-run button — useful when you tweak the prompt and want to retry a bad extraction."""
    return process_view(request, pk)
