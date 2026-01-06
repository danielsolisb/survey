import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.contrib import messages
from .models import Well, SurveyImport, Trajectory
from .utils import process_survey_file
from .visualizer import generate_3d_plot
from .forms import WellForm

class WellCreateView(LoginRequiredMixin, CreateView):
    model = Well
    form_class = WellForm
    template_name = 'surveys/well_form.html'
    success_url = reverse_lazy('surveys:well_list')

    def form_valid(self, form):
        messages.success(self.request, "Pozo creado exitosamente.")
        return super().form_valid(form)

class WellListView(LoginRequiredMixin, ListView):
    model = Well
    template_name = 'surveys/well_list.html'
    context_object_name = 'wells'

from django.db.models import Max
import math

class WellDetailView(LoginRequiredMixin, DetailView):
    model = Well
    template_name = 'surveys/well_detail.html'
    context_object_name = 'well'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Traer importaciones recientes
        context['recent_imports'] = self.object.imports.all().order_by('-created_at')[:5]
        
        # Traer trayectoria activa
        active_traj = self.object.trajectories.filter(is_active=True).first()
        context['active_trajectory'] = active_traj
        
        if active_traj:
            # --- KPIs y Tabla de Datos ---
            stations = active_traj.stations.all().order_by('md')
            context['stations_list'] = stations
            
            # KPI: Inclinación Máxima
            max_inc_data = stations.aggregate(Max('inclination'))
            context['kpi_max_inc'] = max_inc_data.get('inclination__max') or 0
            
            # KPI: Desplazamiento (Closure Distance)
            last_station = stations.last()
            if last_station and last_station.north is not None and last_station.east is not None:
                closure = math.sqrt(last_station.north**2 + last_station.east**2)
                context['kpi_closure'] = closure
            else:
                context['kpi_closure'] = 0

            # Generar Gráfico 3D
            context['plot_div'] = generate_3d_plot(active_traj)
            
        return context

class Well3DView(LoginRequiredMixin, DetailView):
    model = Well
    template_name = 'surveys/well_3d.html'
    context_object_name = 'well'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_traj = self.object.trajectories.filter(is_active=True).first()
        context['active_trajectory'] = active_traj
        
        # Defaults
        context['survey_json'] = '[]'
        context['mechanical_json'] = '[]'
        
        if active_traj:
            # 1. Serializar Trayectoria (Stations)
            # Three.js necesita arrays simples.
            stations = active_traj.stations.all().order_by('md')
            survey_data = []
            for s in stations:
                survey_data.append({
                    'md': float(s.md),
                    'tvd': float(s.tvd) if s.tvd is not None else 0,
                    'north': float(s.north) if s.north is not None else 0,
                    'east': float(s.east) if s.east is not None else 0,
                    'inc': float(s.inclination),
                    'azi': float(s.azimuth)
                })
            context['survey_json'] = json.dumps(survey_data)

            # 2. Serializar Mecánicos (Casing/Liner)
            geometry_items = active_traj.geometry.all().order_by('start_md')
            mech_data = []
            for item in geometry_items:
                mech_data.append({
                    'type': item.item_type,
                    'start_md': float(item.start_md),
                    'end_md': float(item.end_md),
                    'diameter': float(item.diameter),
                    'color': item.color
                })
            context['mechanical_json'] = json.dumps(mech_data)
        
        return context

class SurveyImportView(LoginRequiredMixin, View):
    def post(self, request, pk):
        well = get_object_or_404(Well, pk=pk)
        if 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']
            
            # Crear registro de importación
            survey_import = SurveyImport.objects.create(
                well=well,
                excel_file=excel_file,
                uploaded_by=request.user,
                status=SurveyImport.Status.PENDING
            )
            
            # Procesar archivo (Idealmente esto va a una cola Celery, pero MVP inline)
            success = process_survey_file(survey_import, survey_import.excel_file.path)
            
            if success:
                # Marcar trayectoria como activa si es la única
                trajectory = survey_import.generated_trajectories.first()
                if trajectory:
                    trajectory.is_active = True
                    trajectory.save()

        return redirect('surveys:well_detail', pk=pk)

class DownloadTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        # Ruta al archivo estático (que crearemos en el paso de static)
        file_path = os.path.join(settings.BASE_DIR, 'static', 'templates', 'DynaDrill_Template.xlsx')
        if os.path.exists(file_path):
            return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='DynaDrill_Template.xlsx')
        else:
            return HttpResponse("Plantilla no encontrada. Contacte al administrador.", status=404)
