from django.contrib import admin
from .models import Well, SurveyImport, Trajectory, TrajectoryStation, BoreholeGeometry

class TrajectoryStationInline(admin.TabularInline):
    model = TrajectoryStation
    extra = 0
    readonly_fields = ('tvd', 'north', 'east', 'dls')
    can_delete = False
    ordering = ('md',)
    
    def has_add_permission(self, request, obj=None):
        return False

class BoreholeGeometryInline(admin.TabularInline):
    model = BoreholeGeometry
    extra = 0

@admin.register(Well)
class WellAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'latitude', 'longitude', 'is_active', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('is_active',)

@admin.register(SurveyImport)
class SurveyImportAdmin(admin.ModelAdmin):
    list_display = ('well', 'uploaded_by', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('well__name',)
    readonly_fields = ('processing_log',)

@admin.register(Trajectory)
class TrajectoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'well', 'trajectory_type', 'is_active', 'created_at')
    list_filter = ('well', 'trajectory_type', 'is_active')
    search_fields = ('name', 'well__name')
    inlines = [BoreholeGeometryInline, TrajectoryStationInline]
