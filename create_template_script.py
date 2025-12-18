import pandas as pd
import os

# Definir datos de ejemplo
data_header = {
    'Field': ['Tie-In Depth', 'Tie-In Inclination', 'Tie-In Azimuth', 'Origin Latitude', 'Origin Longitude'],
    'Value': [0, 0, 0, -0.1234, -76.5432],
    'Unit': ['m', 'deg', 'deg', 'deg', 'deg'],
    'Description': ['Profundidad inicial', 'Inclinación inicial', 'Azimut inicial', 'Latitud Origen', 'Longitud Origen']
}

data_survey = {
    'MD': [0, 100, 200, 300],
    'Inc': [0, 0.5, 1.2, 2.5],
    'Azi': [0, 45, 90, 135]
}

data_mechanical = {
    'Item': ['Casing 13-3/8"', 'Casing 9-5/8"', 'Open Hole'],
    'Top_MD': [0, 500, 1500],
    'Bottom_MD': [500, 1500, 3500],
    'Diameter': [13.375, 9.625, 8.5],
    'Color': ['#808080', '#A9A9A9', '#0000FF']
}

# Crear DataFrames
df_header = pd.DataFrame(data_header)
df_survey = pd.DataFrame(data_survey)
df_mech = pd.DataFrame(data_mechanical)

# Guardar en Excel
output_path = 'static/templates/DynaDrill_Template.xlsx'
try:
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_header.to_excel(writer, sheet_name='Header', index=False)
        df_survey.to_excel(writer, sheet_name='Survey', index=False)
        df_mech.to_excel(writer, sheet_name='Mechanical', index=False)
    print(f"Plantilla creada exitosamente en: {output_path}")
except Exception as e:
    print(f"Error creando plantilla: {e}")
