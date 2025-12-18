from django.shortcuts import get_object_or_404, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Trajectory

class TrajectoryDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        trajectory = get_object_or_404(Trajectory, pk=pk)
        well_id = trajectory.well.id
        
        # Eliminar también la importación asociada si existe
        if trajectory.source_import:
            trajectory.source_import.delete() # Esto elimina la trayectoria en cascada si está configurado, pero por seguridad...
        
        # Si no se ha borrado por cascada, borrar manualmente
        if Trajectory.objects.filter(pk=pk).exists():
            trajectory.delete()
            
        messages.success(request, "Trayectoria eliminada correctamente.")
        return redirect('surveys:well_detail', pk=well_id)
