import plotly.graph_objects as go
from probetas_path import probeta_path
import webbrowser
import os

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
    fig.write_html("ruta_puntos_3d.html")
    print("Visualización guardada como 'ruta_puntos_3d.html'. Ábrelo en VS Code para ver la trayectoria interactiva.")
    
    # Abrir automáticamente en el navegador
    html_path = os.path.abspath("ruta_puntos_3d.html")
    webbrowser.open('file://' + html_path)

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
    html_path = os.path.abspath("capas_3d.html")
    fig.write_html(html_path)
    webbrowser.open('file://' + html_path)

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
    html_path = os.path.abspath("toolpaths_3d.html")
    fig.write_html(html_path, auto_open=True)