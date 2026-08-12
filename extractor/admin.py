from django.contrib import admin

from .models import WorkReport, WorkReportRow


class WorkReportRowInline(admin.TabularInline):
    model = WorkReportRow
    extra = 0
    fields = ("row_order", "sr", "bus_no", "mech", "work_done", "material")


@admin.register(WorkReport)
class WorkReportAdmin(admin.ModelAdmin):
    list_display = ("id", "location_name", "report_date", "status", "uploaded_at")
    list_filter = ("status",)
    inlines = [WorkReportRowInline]


@admin.register(WorkReportRow)
class WorkReportRowAdmin(admin.ModelAdmin):
    list_display = ("report", "sr", "bus_no", "mech", "work_done")
    search_fields = ("bus_no", "work_done", "mech")
