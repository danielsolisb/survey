import pandas as pd
import numpy as np
from math import radians, sin, cos, acos, sqrt, degrees, atan2, pi
from .models import Well, SurveyImport, Trajectory, TrajectoryStation, BoreholeGeometry

def minimum_curvature(md1, inc1, azi1, md2, inc2, azi2):
    """
    Calcula el desplazamiento entre dos estaciones usando el método de Curvatura Mínima.
    Retorna delta_norte, delta_este, delta_tvd y dls.
    """
    # Convertir a radianes
    i1, a1 = radians(inc1), radians(azi1)
    i2, a2 = radians(inc2), radians(azi2)
    
    delta_md = md2 - md1
    
    # Calcular Dogleg Angle (beta)
    # cos(beta) = cos(I2-I1) - sin(I1)sin(I2)(1-cos(A2-A1))
    cos_beta = cos(i2 - i1) - (sin(i1) * sin(i2) * (1 - cos(a2 - a1)))
    
    # Proteger contra errores numéricos
    if cos_beta > 1: cos_beta = 1
    if cos_beta < -1: cos_beta = -1
    
    beta = acos(cos_beta)
    
    # Calcular Factor de Ratio (RF)
    if beta < 0.0001: # Segmento recto (o muy pequeño)
        rf = 1
    else:
        rf = 2 / beta * (np.tan(beta / 2))
        
    # Desplazamientos
    delta_north = (delta_md / 2) * (sin(i1) * cos(a1) + sin(i2) * cos(a2)) * rf
    delta_east = (delta_md / 2) * (sin(i1) * sin(a1) + sin(i2) * sin(a2)) * rf
    delta_tvd = (delta_md / 2) * (cos(i1) + cos(i2)) * rf
    
    # Dogleg Severity (deg/30m o deg/100ft) - Usaremos norma métrica deg/30m
    if delta_md == 0:
        dls = 0
    else:
        dls = (degrees(beta) * 30) / delta_md

    return delta_north, delta_east, delta_tvd, dls

def process_survey_file(survey_import, file_path):
    """
    Procesa el archivo Excel cargado.
    1. Lee 'Header' (Opcional, si no asume 0,0,0)
    2. Lee 'Survey' (MD, Inc, Azi) -> Calcula TrajectoryStations
    3. Lee 'Mechanical' -> Crea BoreholeGeometry
    """
    import_log = []
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # --- 1. Crear Trayectoria ---
        trajectory = Trajectory.objects.create(
            well=survey_import.well,
            source_import=survey_import,
            name=f"Importado {survey_import.created_at.strftime('%d/%m %H:%M')}",
            trajectory_type=Trajectory.Type.REAL
        )
        import_log.append("Trayectoria creada.")

        # --- 2. Procesar Datos de Survey ---
        if 'Survey' not in xls.sheet_names:
            raise ValueError("Falta la hoja 'Survey' en el archivo.")
            
        df_survey = pd.read_excel(xls, 'Survey')
        required_cols = ['MD', 'Inc', 'Azi']
        if not all(col in df_survey.columns for col in required_cols):
            raise ValueError(f"La hoja Survey debe tener columnas: {required_cols}")

        df_survey = df_survey.sort_values('MD')
        
        # Inicializar cálculos
        current_n, current_e, current_tvd = 0.0, 0.0, 0.0
        prev_md, prev_inc, prev_azi = 0.0, 0.0, 0.0 
        
        # Si hay Tie-In en Header, leerlo aquí (simplificado a 0 por ahora)
        
        stations_to_create = []
        
        for index, row in df_survey.iterrows():
            md = float(row['MD'])
            inc = float(row['Inc'])
            azi = float(row['Azi'])
            
            if index == 0 and md == 0:
                # Tie-in point en superficie
                d_n, d_e, d_tvd, dls = 0, 0, 0, 0
            else:
                d_n, d_e, d_tvd, dls = minimum_curvature(prev_md, prev_inc, prev_azi, md, inc, azi)
                current_n += d_n
                current_e += d_e
                current_tvd += d_tvd
            
            stations_to_create.append(TrajectoryStation(
                trajectory=trajectory,
                md=md, inclination=inc, azimuth=azi,
                tvd=current_tvd, north=current_n, east=current_e, dls=dls
            ))
            
            prev_md, prev_inc, prev_azi = md, inc, azi
            
        TrajectoryStation.objects.bulk_create(stations_to_create)
        import_log.append(f"Procesados {len(stations_to_create)} puntos de survey.")

        # --- 3. Procesar Mecánica (Opcional) ---
        if 'Mechanical' in xls.sheet_names:
            df_mech = pd.read_excel(xls, 'Mechanical')
            mech_cols = ['Item', 'Top_MD', 'Bottom_MD', 'Diameter', 'Color']
            
            if all(col in df_mech.columns for col in mech_cols):
                geometries = []
                for _, row in df_mech.iterrows():
                    # Validación y Sanitización de Diametro
                    raw_diameter = row['Diameter']
                    try:
                        # Manejar casos donde llega como string con coma (ej: "9,625")
                        if isinstance(raw_diameter, str):
                            raw_diameter = raw_diameter.replace(',', '.')
                        
                        diameter_val = float(raw_diameter)
                        
                        # Heurística: Si el diámetro es > 100 pulgadas (ej: 9625), asumir error de escala/formato y corregir
                        # Tuberías reales de pozo raramente exceden 36-40 pulgadas.
                        if diameter_val > 100:
                            diameter_val = diameter_val / 1000.0
                            
                    except (ValueError, TypeError):
                        diameter_val = 8.5 # Valor fallback seguro
                        
                    geometries.append(BoreholeGeometry(
                        trajectory=trajectory,
                        item_type=row['Item'],
                        start_md=row['Top_MD'],
                        end_md=row['Bottom_MD'],
                        diameter=diameter_val,
                        color=str(row['Color'])
                    ))
                BoreholeGeometry.objects.bulk_create(geometries)
                import_log.append(f"Cargados {len(geometries)} elementos mecánicos.")
            else:
                import_log.append("Hoja Mechanical ignorada: Faltan columnas.")

        survey_import.status = SurveyImport.Status.PROCESSED
        survey_import.processing_log = "\n".join(import_log)
        survey_import.save()
        return True

    except Exception as e:
        survey_import.status = SurveyImport.Status.ERROR
        survey_import.processing_log = f"Error Crítico: {str(e)}"
        survey_import.save()
        return False
