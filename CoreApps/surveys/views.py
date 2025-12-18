import os
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, FileResponse
from django.conf import settings
from .models import Well, SurveyImport
from .utils import process_survey_file
from .visualizer import generate_3d_plot

class WellListView(LoginRequiredMixin, ListView):
    model = Well
    template_name = 'surveys/well_list.html'
    context_object_name = 'wells'

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
        
        # Generar Gráfico 3D si hay trayectoria
        if active_traj:
            context['plot_div'] = generate_3d_plot(active_traj)
            
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
