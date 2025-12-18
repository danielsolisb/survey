import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Well(models.Model):
    """
    Modelo que representa un Pozo Petrolero.
    Actúa como entidad raíz para todos los surveys.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Nombre del Pozo"), max_length=100, unique=True)
    location = models.CharField(_("Ubicación/Campo"), max_length=150, blank=True)
    
    # Coordenadas de Superficie (Origen 0,0,0 local)
    latitude = models.FloatField(_("Latitud"), null=True, blank=True)
    longitude = models.FloatField(_("Longitud"), null=True, blank=True)
    elevation = models.FloatField(_("Elevación (GL/RKB)"), default=0.0, help_text=_("Metros sobre nivel del mar"))

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Pozo")
        verbose_name_plural = _("Pozos")
        ordering = ['name']

    def __str__(self):
        return self.name

class SurveyImport(models.Model):
    """
    Registro de auditoría de archivos subidos.
    Guarda el archivo original para re-procesamiento.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pendiente')
        PROCESSED = 'PROCESSED', _('Procesado Exitosamente')
        ERROR = 'ERROR', _('Error en Procesamiento')

    well = models.ForeignKey(Well, on_delete=models.CASCADE, related_name='imports')
    excel_file = models.FileField(_("Archivo Excel"), upload_to='surveys/raw/%Y/%m/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Subido por"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    processing_log = models.TextField(_("Log de Procesamiento"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Importación de Survey")
        verbose_name_plural = _("Importaciones")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.well.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Trajectory(models.Model):
    """
    Representa un 'Survey' específico o una versión de planificación.
    Un pozo puede tener múltiples trayectorias (Plan vs Real, o diferentes corridas).
    """
    class Type(models.TextChoices):
        REAL = 'REAL', _('Survey Real (MWD/Gyro)')
        PLAN = 'PLAN', _('Planificación')

    well = models.ForeignKey(Well, on_delete=models.CASCADE, related_name='trajectories')
    source_import = models.ForeignKey(SurveyImport, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_trajectories')
    
    name = models.CharField(_("Nombre de Trayectoria"), max_length=100, help_text=_("Ej: Definitivo Rev.1, Plan #2"))
    trajectory_type = models.CharField(max_length=10, choices=Type.choices, default=Type.REAL)
    
    # Parámetros de Geodesia
    mag_declination = models.FloatField(_("Declinación Magnética"), default=0.0, help_text="Corrección Norte Mag -> Geo")
    grid_convergence = models.FloatField(_("Convergencia de Cuadrícula"), default=0.0, help_text="Corrección Geo -> Grid")
    
    is_active = models.BooleanField(_("Es Trayectoria Principal"), default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Trayectoria")
        verbose_name_plural = _("Trayectorias")
        unique_together = ['well', 'name'] # Evitar nombres duplicados en el mismo pozo

    def __str__(self):
        return f"{self.name} ({self.get_trajectory_type_display()})"

class TrajectoryStation(models.Model):
    """
    Punto individual de medición (Estación).
    Contiene datos RAW (Input) y Calculados (Output).
    """
    trajectory = models.ForeignKey(Trajectory, on_delete=models.CASCADE, related_name='stations')
    
    # Input Data (Leído del Excel)
    md = models.FloatField(_("MD (m)"), help_text="Measured Depth")
    inclination = models.FloatField(_("Inc (deg)"), help_text="Inclinación")
    azimuth = models.FloatField(_("Azi (deg)"), help_text="Azimuth")

    # Calculated Data (Minimum Curvature)
    tvd = models.FloatField(_("TVD (m)"), null=True, blank=True, help_text="True Vertical Depth")
    north = models.FloatField(_("Norte (m)"), null=True, blank=True, help_text="Desplazamiento Norte")
    east = models.FloatField(_("Este (m)"), null=True, blank=True, help_text="Desplazamiento Este")
    dls = models.FloatField(_("DLS"), null=True, blank=True, help_text="Dogleg Severity")

    # Atributos Mecánicos / Flexibles para Mapa de Calor
    # Guardamos como JSON para flexibilidad futura (Fricción, Tortuosidad, etc)
    attributes = models.JSONField(_("Atributos Mecánicos"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Estación")
        verbose_name_plural = _("Estaciones")
        ordering = ['md']
        indexes = [
            models.Index(fields=['trajectory', 'md']),
        ]

    def __str__(self):
        return f"{self.md}m"

class BoreholeGeometry(models.Model):
    """
    Define la geometría física del pozo (Casings, Liners, Open Hole).
    Esencial para la visualización 3D (diámetro y color del tubo).
    """
    trajectory = models.ForeignKey(Trajectory, on_delete=models.CASCADE, related_name='geometry')
    
    item_type = models.CharField(_("Tipo de Elemento"), max_length=50, help_text="Casing, Liner, Open Hole, Tubing")
    start_md = models.FloatField(_("Profundidad Inicial (MD)"))
    end_md = models.FloatField(_("Profundidad Final (MD)"))
    diameter = models.FloatField(_("Diámetro (in)"), help_text="Diámetro nominal para visualización")
    color = models.CharField(_("Color Hex"), max_length=20, default="#808080", help_text="Color para el 3D (ej: #FF0000)")

    class Meta:
        verbose_name = _("Geometría del Pozo")
        verbose_name_plural = _("Geometría del Pozo")
        ordering = ['start_md']

    def __str__(self):
        return f"{self.item_type} ({self.start_md}-{self.end_md}m)"
