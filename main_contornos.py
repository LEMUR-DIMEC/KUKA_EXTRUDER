from patterns.translate_KRL import KRLTranslator
from visualizadores import visualize_path_3d
from slicer import coordenadas_stl
from visualizadores import visualize_layers_3d
from visualizadores import visualize_positions_progressive
from slicer import generate_all_toolpaths
from slicer import compute_part_bounds_xy, compute_sacrificial_point
from slicer import apply_solution_1_gap_trim, apply_solution_2_sacrificial_tab

stl = "Geometrías_contornos/cilindro.stl"
altura_capa = 2
z_offset = 2
# ---------------------------------------------------------------------
# Selector de solución para el problema de "inicio == fin" en la costura:
#   0 -> Sin corrección (comportamiento original, con el problema)
#   1 -> Recorte del cierre (termina `SEAM_DELTA` mm antes de cerrar)
#   2 -> Segmento de sacrificio pegado a la costura (impresión continua)
# Cambia SOLUCION para probar cada una sobre tu STL real.
# ---------------------------------------------------------------------
SOLUCION = 1

SEAM_DELTA = 3.5          # Solución 1: mm que se recortan antes de cerrar
TAB_LENGTH = 10.0         # Solución 2: largo del segmento de sacrificio
TAB_SEPARATION = 2.0      # Solución 2: separación entre ida y vuelta
SEAM_REFERENCE = None     # (x, y) fijo para la costura, o None = usar el
                           # primer punto de la primera capa como referencia

# ---------------------------------------------------------------------
# Camino previo (línea de sacrificio POR CAPA, hacia un punto fuera de la
# pieza, antes de bajar al punto de inicio real de la capa). Es
# independiente de SOLUCION: aplica igual con 0, 1 o 2.
#   True  -> comportamiento original: viaja a sac_punto (afuera, según
#            `sacrificio_margen`), ceba ahí y entra en línea recta
#            extruyendo hasta el punto de inicio.
#   False -> sin desvío: sube en seco justo sobre el punto de inicio de
#            la capa, baja, y ceba ahí mismo (sin acercamiento en ángulo).
# ---------------------------------------------------------------------
USAR_CAMINO_PREVIO = False


def codigo_contornos(poses, vent=1, temp=200, vel=0.035, t_enf = 2, t_retracción = 0.6,
                      sacrificio_margen=30.0, usar_camino_previo=True):
        filename = "cilindro"
        filename_export = "Archivos_KRL/Contorno_KRL/" 

        # Centroide XY y radio máximo de la pieza completa (todas las capas).
        # Se calcula UNA sola vez y se reutiliza en cada cambio de capa para
        # ubicar el punto de sacrificio siempre fuera de la figura.
        centroid_xy, max_radius = compute_part_bounds_xy(poses)


        krl = KRLTranslator(filename, axis_vel=[
                        15, 15, 15, 15, 15, 15], speed_ms=vel)
        krl.create_KRL_file(filename_export)

        RPM = int(vel * 1000)
        
        krl.add_line_to_src_file("; OUT[TEMP] = " + str(temp) + " \n")
        krl.add_line_to_src_file("; OUT[vent] = " + str(vent) + " \n")
        krl.add_line_to_src_file("; OUT[RPM] = " + str(RPM) + " \n")

        
        krl.add_line_to_src_file("$OUT[1] = TRUE \n")
        krl.add_line_to_src_file("WAIT SEC 20" "\n")
        krl.add_line_to_src_file("$OUT[1] = FALSE \n")

        krl.add_line_to_src_file("; USER POSES CALLS \n")
        krl.add_line_to_src_file("PTP {X 75, Y 30, Z 420, A 0, B 90, C 0} \n")  # COI
        krl.add_line_to_src_file("; USER POSES CALLS \n")

        for i, capa in enumerate(poses):
                if not capa or not capa[0]:
                        continue

                primer_punto = capa[0][0]

                if usar_camino_previo:
                        sac_punto = compute_sacrificial_point(
                                primer_punto, centroid_xy, max_radius,
                                margin=sacrificio_margen
                        )

                        # --- Línea de sacrificio (purga que SE CONECTA con la pieza) ---
                        # 1) Viaja elevado (Z+5) y en seco hasta el punto de purga,
                        #    ubicado fuera del radio de la figura.
                        krl.add_line_to_src_file("LIN {X " + str(sac_punto[0]) + ", Y " + str(sac_punto[1]) + ", Z " + str(
                                sac_punto[2] - altura_capa) + ", A 0, B 90, C 0} C_DIS\n")
                        krl.add_line_to_src_file("WAIT SEC " + str(t_enf) + "\n")

                        # 2) Baja a la Z real de la capa, todavía sin extruir.
                        krl.add_line_to_src_file("LIN {X " + str(sac_punto[0]) + ", Y " + str(sac_punto[1]) + ", Z " + str(
                                sac_punto[2]) + ", A 0, B 90, C 0} C_DIS\n")

                        # 3) Activa la extrusión y espera el tiempo de retracción
                        #    (cebado) ahí mismo, ya a la altura de impresión.
                        krl.add_line_to_src_file("$OUT[1] = TRUE \n")
                        krl.add_line_to_src_file("WAIT SEC " + str(t_retracción) + "\n")

                        # 4) Traza en línea recta, EXTRUYENDO, desde el punto de
                        #    purga hasta el primer punto real de la capa. Esta línea
                        #    conecta físicamente con la figura: el flujo ya llega
                        #    estable justo cuando arranca el contorno real, en vez
                        #    de reiniciar la extrusión sobre el propio modelo.
                        krl.add_line_to_src_file("LIN {X " + str(primer_punto[0]) + ", Y " + str(primer_punto[1]) + ", Z " + str(
                                primer_punto[2]) + ", A 0, B 90, C 0} C_DIS\n")
                else:
                        # --- Sin camino previo: acercamiento directo, sin desvío ---
                        # Sube en seco justo encima del punto de inicio real de la
                        # capa (sin pasar por un punto de purga aparte), baja, y
                        # ceba la extrusión ahí mismo.
                        krl.add_line_to_src_file("LIN {X " + str(primer_punto[0]) + ", Y " + str(primer_punto[1]) + ", Z " + str(
                                primer_punto[2] - altura_capa) + ", A 0, B 90, C 0} C_DIS\n")
                        krl.add_line_to_src_file("WAIT SEC " + str(t_enf) + "\n")

                        krl.add_line_to_src_file("LIN {X " + str(primer_punto[0]) + ", Y " + str(primer_punto[1]) + ", Z " + str(
                                primer_punto[2]) + ", A 0, B 90, C 0} C_DIS\n")

                        krl.add_line_to_src_file("$OUT[1] = TRUE \n")
                        krl.add_line_to_src_file("WAIT SEC " + str(t_retracción) + "\n")

                for j, contour in enumerate(capa):
                        # Bajada al inicio del contorno (a su Z real, sin offset)
                        krl.add_line_to_src_file("LIN {X " + str(contour[0][0]) + ", Y " + str(contour[0][1]) + ", Z " + str(
                                contour[0][2]) + ", A 0, B 90, C 0} C_DIS\n")

                        for k, pose in enumerate(contour):
                                krl.add_line_to_src_file("LIN {X " + str(pose[0]) + ", Y " + str(pose[1]) + ", Z " + str(
                                        pose[2]) + ", A 0, B 90, C 0} C_DIS\n")

                # Apagar extrusión al terminar la capa, antes de subir a la siguiente
                krl.add_line_to_src_file("$OUT[1] = FALSE \n")
                krl.add_line_to_src_file("\n")
                krl.add_line_to_src_file("; END LAYER " + str(i) + " \n")

        print(f"Archivo KRL generado: {filename_export}{filename}.src")

coordinates, all_layers, layers_z = coordenadas_stl(stl, altura_capa, z_offset)

# ---------------------------------------------------------------------
# Aplicar la solución elegida al problema de costura ANTES de generar el
# código KRL. Ambas funciones dejan `positions` con la misma estructura
# anidada (capas -> contornos -> puntos) que espera codigo_contornos(),
# así que no hace falta tocar nada más abajo.
# ---------------------------------------------------------------------
if SOLUCION == 1:
        positions = apply_solution_1_gap_trim(
                coordinates, delta=SEAM_DELTA, seam_reference=SEAM_REFERENCE
        )
        print(f"✓ Solución 1 aplicada: costura fija + recorte de cierre (delta={SEAM_DELTA} mm)")
elif SOLUCION == 2:
        positions = apply_solution_2_sacrificial_tab(
                coordinates, tab_length=TAB_LENGTH, tab_separation=TAB_SEPARATION,
                seam_reference=SEAM_REFERENCE
        )
        print(f"✓ Solución 2 aplicada: costura fija + segmento de sacrificio "
              f"(largo={TAB_LENGTH} mm, separación={TAB_SEPARATION} mm)")
else:
        positions = coordinates
        print("⚠ Sin corrección de costura (SOLUCION=0): puede haber exceso de material en el cierre.")

# Visualizar capas
visualize_layers_3d(all_layers, layers_z)

# Generar todas las rutas de herramienta
toolpaths = generate_all_toolpaths(all_layers)

#visualize_positions_progressive(positions, output_file="posiciones_progresivas.html", delay=50)

codigo_contornos(positions, usar_camino_previo=USAR_CAMINO_PREVIO)