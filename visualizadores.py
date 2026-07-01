import plotly.graph_objects as go
from probetas_path import probeta_path
import webbrowser
import os
from pathlib import Path


def _get_project_root():
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "README.md").exists() or (candidate / ".git").exists():
            return str(candidate)
    return str(current.parent)


PROJECT_ROOT = _get_project_root()
HTML_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "html_outputs")
os.makedirs(HTML_OUTPUT_DIR, exist_ok=True)


def _resolve_html_output_path(output_file):
    if output_file is None:
        output_file = "visualizacion.html"

    if os.path.isabs(output_file):
        target_path = output_file
    else:
        target_path = os.path.join(HTML_OUTPUT_DIR, os.path.basename(output_file))

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    return target_path


def visualize_path_3d(positions):
    """
    Visualiza la ruta de puntos en 3D usando Plotly.
    Muestra puntos conectados por líneas para representar la trayectoria.
    """
    fig = go.Figure()

    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

    for i, capa in enumerate(positions):
        color = colors[i % len(colors)]

        # Extraer coordenadas
        xs = [x[0] for x in capa]
        ys = [x[1] for x in capa]
        zs = [x[2] for x in capa]

        # Agregar puntos
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode='markers+lines',
            marker=dict(size=4, color=color),
            line=dict(color=color, width=2),
            name=f'Capa {i}',
            text=[f'Punto {j}: ({x:.2f}, {y:.2f}, {z:.2f})' for j, (x, y, z) in enumerate(zip(xs, ys, zs))]
        ))

    # Configurar el layout
    fig.update_layout(
        title="Ruta de Puntos 3D - Trayectoria del Robot KUKA",
        scene=dict(
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
            xaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', showbackground=True, backgroundcolor='rgb(230, 230,230)'),
            yaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', showbackground=True, backgroundcolor='rgb(230, 230,230)'),
            zaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', showbackground=True, backgroundcolor='rgb(230, 230,230)'),
        ),
        margin=dict(r=10, b=10, l=10, t=10)
    )

    # Mostrar la figura
    # fig.show()  # Comentado para no abrir en navegador

    # También guardar como HTML para visualización persistente
    html_path = _resolve_html_output_path("ruta_puntos_3d.html")
    fig.write_html(html_path)
    print(f"Visualización guardada en '{os.path.relpath(html_path, PROJECT_ROOT)}'.")

    # Abrir automáticamente en el navegador
    webbrowser.open('file://' + os.path.abspath(html_path))

# -------------------------
# Función de visualización
# -------------------------
def visualize_layers_3d(all_layers, layers_z):
    fig = go.Figure()

    for i, (polygons, z) in enumerate(zip(all_layers, layers_z)):
        for j, polygon in enumerate(polygons):
            # polygon es un shapely Polygon, obtener coordenadas
            if polygon is not None:
                x, y = polygon.exterior.xy
                xs = list(x)
                ys = list(y)
                zs = [z] * len(xs)

                # Agregar línea cerrada
                xs.append(xs[0])
                ys.append(ys[0])
                zs.append(z)

                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=zs,
                    mode='lines',
                    line=dict(width=2),
                    name=f'Capa Z={z:.2f}, Polígono {j}',
                    showlegend=True
                ))

    # Configurar layout
    fig.update_layout(
        title="Capas 3D del Modelo STL",
        scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z',
        ),
        margin=dict(r=10, b=10, l=10, t=10)
    )

    # Guardar HTML antes de abrir
    html_path = _resolve_html_output_path("capas_3d.html")
    fig.write_html(html_path)
    webbrowser.open('file://' + os.path.abspath(html_path))

    # -------------------------
# Función de visualización de rutas de herramienta
# -------------------------
def visualize_toolpaths_3d(toolpaths_data, layers_z_data):
    fig = go.Figure()

    for i, layer_toolpaths in enumerate(toolpaths_data):
        current_z = layers_z_data[i]
        for j, toolpath_coords in enumerate(layer_toolpaths):
            # toolpath_coords is a numpy array of shape (N, 2) for (x, y)
            xs = toolpath_coords[:, 0].tolist()
            ys = toolpath_coords[:, 1].tolist()
            zs = [current_z] * len(xs)

            # Ensure the loop is closed for visualization
            if xs[0] != xs[-1] or ys[0] != ys[-1]:
                xs.append(xs[0])
                ys.append(ys[0])
                zs.append(current_z)

            fig.add_trace(go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode='lines',
                line=dict(width=2),
                name=f'Toolpath Z={current_z:.2f}, Polígono {j}',
                showlegend=False  # Set to False to avoid clutter with many legends
            ))

    # Configurar layout
    fig.update_layout(
        title="Rutas de Herramienta 3D por Capa",
        scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z',
        ),
        margin=dict(r=10, b=10, l=10, t=10)
    )

    # Guardar en HTML y abrir
    html_path = _resolve_html_output_path("toolpaths_3d.html")
    fig.write_html(html_path, auto_open=True)

# -------------------------
# Función de visualización progresiva (animada) - OPTIMIZADA
# -------------------------
def visualize_positions_progressive(positions, output_file="posiciones_progresivas.html", delay=100, frames_interval=5):
    """
    Visualiza la colocación progresiva de puntos de forma optimizada.
    Crea frames cada N puntos para mejorar el rendimiento.
    
    Args:
        positions: Lista de capas, donde cada capa contiene contornos
        output_file: Nombre del archivo HTML de salida
        delay: Retraso en ms entre frames
        frames_interval: Crear un frame cada N puntos (para optimizar)
    """
    import numpy as np
    
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    # Recolectar todos los puntos de forma lineal
    all_points = []
    all_labels = []
    
    for capa_idx, capa in enumerate(positions):
        color = colors[capa_idx % len(colors)]
        for contorno_idx, contorno in enumerate(capa):
            for punto_idx, punto in enumerate(contorno):
                all_points.append(punto)
                all_labels.append(
                    f'Capa {capa_idx}, Contorno {contorno_idx}, Punto {punto_idx}<br>' +
                    f'X: {punto[0]:.2f}, Y: {punto[1]:.2f}, Z: {punto[2]:.2f}'
                )
    
    print(f"  Total de puntos: {len(all_points)}")
    
    # Crear figura con datos iniciales vacíos
    fig = go.Figure()
    
    # Agregar trace inicial vacío
    fig.add_trace(go.Scatter3d(
        x=[], y=[], z=[],
        mode='markers+lines',
        marker=dict(size=5, color='red', opacity=0.8),
        line=dict(color='red', width=2),
        hovertemplate='%{text}<extra></extra>',
        text=[]
    ))
    
    # Crear frames de forma eficiente
    frames = []
    
    # Frame inicial vacío
    frames.append(go.Frame(data=[fig.data[0]], name="Frame 0"))
    
    # Crear frames en intervalos
    frame_num = 1
    for i in range(frames_interval, len(all_points) + frames_interval, frames_interval):
        end_idx = min(i, len(all_points))
        
        frame_points = all_points[:end_idx]
        frame_labels = all_labels[:end_idx]
        
        xs = [p[0] for p in frame_points]
        ys = [p[1] for p in frame_points]
        zs = [p[2] for p in frame_points]
        
        frame = go.Frame(
            data=[go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode='markers+lines',
                marker=dict(size=5, color='blue', opacity=0.8),
                line=dict(color='blue', width=1),
                hovertemplate='%{text}<extra></extra>',
                text=frame_labels
            )],
            name=f"Frame {frame_num}"
        )
        frames.append(frame)
        frame_num += 1
    
    fig.frames = frames
    
    print(f"  Frames generados: {len(frames)}")
    
    # Configurar layout
    fig.update_layout(
        title="Colocación Progresiva de Puntos - Visualización en Tiempo Real",
        scene=dict(
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
            xaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', 
                      showbackground=True, backgroundcolor='rgb(230, 230, 230)'),
            yaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', 
                      showbackground=True, backgroundcolor='rgb(230, 230, 230)'),
            zaxis=dict(gridcolor='rgb(255, 255, 255)', zerolinecolor='rgb(255, 255, 255)', 
                      showbackground=True, backgroundcolor='rgb(230, 230, 230)'),
        ),
        updatemenus=[{
            'type': 'buttons',
            'showactive': False,
            'buttons': [
                {
                    'label': '▶ Reproducir',
                    'method': 'animate',
                    'args': [None, {'frame': {'duration': delay, 'redraw': True}, 
                                   'fromcurrent': True, 'mode': 'immediate'}]
                },
                {
                    'label': '⏸ Pausar',
                    'method': 'animate',
                    'args': [[None], {'frame': {'duration': 0, 'redraw': False}, 
                                     'mode': 'immediate', 'transition': {'duration': 0}}]
                }
            ]
        }],
        margin=dict(r=10, b=10, l=10, t=50),
        height=800
    )
    
    # Guardar en HTML
    html_path = _resolve_html_output_path(output_file)
    print(f"  Guardando archivo HTML...")
    fig.write_html(html_path)

    print(f"✓ Visualización progresiva guardada como '{os.path.relpath(html_path, PROJECT_ROOT)}'")
    print(f"  Abre el archivo en el navegador para ver la animación")
    
    # Abrir automáticamente en el navegador
    try:
        webbrowser.open('file://' + html_path)
    except:
        pass
    
    return html_path


# -------------------------
# Visualización del recorrido YA OPTIMIZADO (orden final determinado)
# -------------------------
def visualize_optimized_route_3d(coordinates, output_file="ruta_optimizada_3d.html", open_browser=True):
    """
    Visualiza el recorrido final (después de optimizar el orden de contornos
    y capas) como UNA sola polilínea continua, coloreada según el orden de
    recorrido (del primer punto al último). Esto permite verificar visualmente
    que la ruta sigue el contorno de forma continua y no "salta" de un lado a
    otro dentro de la misma capa/contorno.

    Args:
        coordinates: Lista de capas -> lista de contornos -> lista de puntos (x, y, z).
                     Es exactamente el `coordinates` que devuelve coordenadas_stl()
                     o optimize_all_layers_path().
        output_file: Nombre del archivo HTML de salida.
        open_browser: Si True, abre el archivo automáticamente en el navegador.
    """
    # Aplanar todo en un solo recorrido ordenado, guardando en qué capa/contorno
    # está cada punto (para el hover text y para marcar transiciones).
    xs, ys, zs, labels = [], [], [], []
    order_idx = []  # índice de recorrido -> usado como color (degradado)
    transition_x, transition_y, transition_z = [], [], []  # saltos entre contornos/capas

    punto_global = 0
    prev_point = None
    for capa_idx, capa in enumerate(coordinates):
        for contorno_idx, contorno in enumerate(capa):
            if not contorno:
                continue
            # Marcar el salto (línea punteada) entre el fin de un contorno y
            # el inicio del siguiente, para distinguirlo del recorrido normal.
            if prev_point is not None:
                transition_x += [prev_point[0], contorno[0][0], None]
                transition_y += [prev_point[1], contorno[0][1], None]
                transition_z += [prev_point[2], contorno[0][2], None]

            for punto_idx, punto in enumerate(contorno):
                xs.append(punto[0])
                ys.append(punto[1])
                zs.append(punto[2])
                order_idx.append(punto_global)
                labels.append(
                    f'Orden: {punto_global} | Capa {capa_idx}, Contorno {contorno_idx}, Punto {punto_idx}<br>'
                    f'X: {punto[0]:.2f}, Y: {punto[1]:.2f}, Z: {punto[2]:.2f}'
                )
                punto_global += 1

            prev_point = contorno[-1]

    fig = go.Figure()

    # Recorrido real (dentro de cada contorno), coloreado por orden de visita
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='lines+markers',
        marker=dict(
            size=3,
            color=order_idx,
            colorscale='Viridis',
            colorbar=dict(title="Orden de recorrido"),
        ),
        line=dict(color='rgba(80,80,80,0.6)', width=3),
        hovertemplate='%{text}<extra></extra>',
        text=labels,
        name='Recorrido optimizado'
    ))

    # Transiciones/saltos entre contornos o capas, resaltados en rojo punteado
    if transition_x:
        fig.add_trace(go.Scatter3d(
            x=transition_x, y=transition_y, z=transition_z,
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            name='Transiciones entre contornos/capas',
            hoverinfo='skip'
        ))

    # Marcar inicio y fin
    if xs:
        fig.add_trace(go.Scatter3d(
            x=[xs[0]], y=[ys[0]], z=[zs[0]],
            mode='markers', marker=dict(size=8, color='green', symbol='diamond'),
            name='Inicio'
        ))
        fig.add_trace(go.Scatter3d(
            x=[xs[-1]], y=[ys[-1]], z=[zs[-1]],
            mode='markers', marker=dict(size=8, color='black', symbol='x'),
            name='Fin'
        ))

    fig.update_layout(
        title="Recorrido Final Optimizado (color = orden de visita)",
        scene=dict(
            xaxis_title='X (mm)',
            yaxis_title='Y (mm)',
            zaxis_title='Z (mm)',
        ),
        margin=dict(r=10, b=10, l=10, t=40),
        height=800
    )

    html_path = _resolve_html_output_path(output_file)
    fig.write_html(html_path)
    print(f"✓ Visualización del recorrido optimizado guardada como '{os.path.relpath(html_path, PROJECT_ROOT)}'")

    if open_browser:
        try:
            webbrowser.open('file://' + html_path)
        except Exception:
            pass

    return html_path