import numpy as np
import plotly.graph_objects as go
from plotly import offline
from .models import Trajectory

def generate_3d_plot(trajectory):
    """
    Genera un gráfico 3D interactivo del pozo usando Plotly.
    Adapta la lógica de cilindros para dar volumen al pozo según su geometría.
    Retorna un string HTML (div) listo para incrustar.
    """
    stations = trajectory.stations.all().order_by('md')
    geometry = trajectory.geometry.all().order_by('start_md')
    
    if not stations.exists():
        return "<div class='text-center text-slate-500 py-10'>Sin datos de survey para visualizar.</div>"

    # Extraer coordinadas
    # Nota: Plotly usa coordenadas (X, Y, Z). 
    # En petróleo: X=Este, Y=Norte, Z=TVD (Invertido).
    
    # Convertir a numpy arrays para velocidad
    md_arr = np.array([s.md for s in stations])
    tvd_arr = np.array([s.tvd for s in stations])
    north_arr = np.array([s.north for s in stations])
    east_arr = np.array([s.east for s in stations])
    
    fig = go.Figure()

    # Constantes de Visualización
    # Factor ajustado a 50.0 para balancear visibilidad y realismo (similar al script original)
    VISUAL_EXAGGERATION_FACTOR = 50.0  
    RADIAL_RESOLUTION = 20

    def create_3d_cylinder(x, y, z, r, color_vals, name):
        theta = np.linspace(0, 2*np.pi, RADIAL_RESOLUTION)
        theta_grid, z_grid = np.meshgrid(theta, z)
        x_grid = np.array([xi + r * np.cos(theta) for xi in x])
        y_grid = np.array([yi + r * np.sin(theta) for yi in y])
        color_grid = np.tile(color_vals, (RADIAL_RESOLUTION, 1)).T
        
        return go.Surface(
            x=x_grid, y=y_grid, z=z_grid,
            surfacecolor=color_grid,
            colorscale='Turbo',
            name=name,
            showscale=False,
            opacity=1.0, 
            # Iluminación ajustada para resaltar volumen cilíndrico
            lighting=dict(ambient=0.3, diffuse=0.9, roughness=0.1, specular=1.0, fresnel=0.5),
            hoverinfo="text",
            text=f"{name} (OD: {r/VISUAL_EXAGGERATION_FACTOR*12*2:.3f}\")", 
            showlegend=True 
        )

    # --- HELPER: Interpolación para segmentos exactos ---
    def get_path_segment(start_md, end_md):
        """
        Retorna arrays (e, n, t, r) para el rango solicitado,
        interpolando los puntos extremos para que el tubo cubra exactamente el rango.
        """
        # 1. Encontrar índices base
        # Puntos dentro del rango estricto
        mask_d = (md_arr >= start_md) & (md_arr <= end_md)
        e_seg = east_arr[mask_d]
        n_seg = north_arr[mask_d]
        t_seg = tvd_arr[mask_d]
        m_seg = md_arr[mask_d]
        
        # Lista para construir el segmento final
        final_e, final_n, final_t, final_m = [], [], [], []
        
        # 2. Interpolación del punto INICIAL (si start_md no coincide con el primer punto)
        if len(m_seg) == 0 or m_seg[0] > start_md:
            # Encontrar el índice anterior a start_md
            idx_prev = np.searchsorted(md_arr, start_md) - 1
            if idx_prev >= 0 and idx_prev < len(md_arr) - 1:
                # Interpolamos entre idx_prev y idx_prev+1
                m0, m1 = md_arr[idx_prev], md_arr[idx_prev+1]
                factor = (start_md - m0) / (m1 - m0) if m1 > m0 else 0
                
                final_e.append(east_arr[idx_prev] + (east_arr[idx_prev+1] - east_arr[idx_prev]) * factor)
                final_n.append(north_arr[idx_prev] + (north_arr[idx_prev+1] - north_arr[idx_prev]) * factor)
                final_t.append(tvd_arr[idx_prev] + (tvd_arr[idx_prev+1] - tvd_arr[idx_prev]) * factor)
                final_m.append(start_md)
        
        # 3. Agregar puntos intermedios existentes
        final_e.extend(e_seg)
        final_n.extend(n_seg)
        final_t.extend(t_seg)
        final_m.extend(m_seg)
        
        # 4. Interpolación del punto FINAL (si end_md no coincide con el último punto)
        if len(final_m) > 0 and final_m[-1] < end_md:
             idx_prev = np.searchsorted(md_arr, end_md) - 1
             if idx_prev >= 0 and idx_prev < len(md_arr) - 1:
                m0, m1 = md_arr[idx_prev], md_arr[idx_prev+1]
                factor = (end_md - m0) / (m1 - m0) if m1 > m0 else 0
                
                final_e.append(east_arr[idx_prev] + (east_arr[idx_prev+1] - east_arr[idx_prev]) * factor)
                final_n.append(north_arr[idx_prev] + (north_arr[idx_prev+1] - north_arr[idx_prev]) * factor)
                final_t.append(tvd_arr[idx_prev] + (tvd_arr[idx_prev+1] - tvd_arr[idx_prev]) * factor)
                final_m.append(end_md)
        
        return np.array(final_e), np.array(final_n), np.array(final_t)

    # Si no hay geometría, cilindro único
    if not geometry.exists():
        r_viz = ((8.5/2)/12) * VISUAL_EXAGGERATION_FACTOR
        cyl = create_3d_cylinder(east_arr, north_arr, tvd_arr, r_viz, tvd_arr, "Open Hole")
        fig.add_trace(cyl)
        fig.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode='markers', name='Open Hole 8.5"', marker=dict(size=15, color='#1f77b4', symbol='square')))
    
    else:
        # Lógica "Telescópica" (Layering)
        # Dibujamos CADA elemento independientemente. 
        # Los tubos más anchos (Casings superficiales) cubrirán a los internos si se superponen.
        # Esto replica exactamente el comportamiento del script de Python del usuario.
        
        legend_items = set()

        for item in geometry:
            # Obtener segmento interpolado exacto para este item
            s_e, s_n, s_t = get_path_segment(item.start_md, item.end_md)
            
            if len(s_e) > 1:
                radius_ft = (item.diameter / 2) / 12
                r_viz = radius_ft * VISUAL_EXAGGERATION_FACTOR
                
                # Nombre para hover
                label = f"{item.item_type} ({item.diameter}\")"
                
                # Crear cilindro
                cyl = create_3d_cylinder(s_e, s_n, s_t, r_viz, s_t, label)
                fig.add_trace(cyl)
                
                # Agregar a leyenda (evitando duplicados)
                if label not in legend_items:
                    fig.add_trace(go.Scatter3d(
                        x=[None], y=[None], z=[None], mode='markers', 
                        name=label, 
                        marker=dict(size=12, color=item.color if item.color else 'blue', symbol='square')
                    ))
                    legend_items.add(label)

    # Configuración de Escena DARK MODE
    fig.update_layout(
        autosize=True,
        height=700,
        margin=dict(l=10, r=10, b=80, t=50),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.05,
            xanchor="center", x=0.5,
            font=dict(color="white", size=12),
            bgcolor="rgba(0,0,0,0)",
            itemsizing='constant'
        ),
        title=dict(text=f"Visualización 3D: {trajectory.name}", font=dict(color="white", size=18)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        scene=dict(
            aspectmode='data',
            xaxis=dict(title='Este (X)', color="white", backgroundcolor="rgba(30, 41, 59, 0.5)", gridcolor="gray", showbackground=True),
            yaxis=dict(title='Norte (Y)', color="white", backgroundcolor="rgba(30, 41, 59, 0.5)", gridcolor="gray", showbackground=True),
            zaxis=dict(title='TVD (Z)', autorange='reversed', color="white", backgroundcolor="rgba(30, 41, 59, 0.5)", gridcolor="gray", showbackground=True),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=0.5) # Mejor ángulo inicial
            )
        ),
    )

    # Retornar div HTML (incluyendo JS por si acaso, o manejarlo externo)
    return offline.plot(fig, output_type='div', include_plotlyjs='cdn')
