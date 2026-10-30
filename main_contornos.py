from patterns.translate_KRL import KRLTranslator
from visualizadores import visualize_path_3d
from slicer import coordenadas_stl
from visualizadores import visualize_layers_3d
from visualizadores import visualize_positions_progressive
from slicer import generate_all_toolpaths
from slicer import apply_solution

stl = "Geometrías_contornos/cilindro.stl"
altura_capa = 2
z_offset = 2 #En caso de que la pieza no esté centrada en el origen, se puede usar un offset en Z para que la primera capa quede a la altura deseada.

SEAM_DELTA = 3.5          #Distancia mínima entre el último punto de un contorno y el primer punto del mismo contorno
                          # primer punto de la primera capa como referencia


def codigo_contornos(poses, vent=1, temp=200, vel=0.025, t_enf = 3, t_retracción = 0.8):
        filename = "cilindro" #Colocar el nombre que se quiera para el archivo KRL generado.
        filename_export = "Archivos_KRL/Contorno_KRL/" #Colocar la ruta donde se quiere guardar el archivo KRL generado.

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

                # Sube en seco justo encima del punto de inicio real de la
                # capa, baja, y ceba la extrusión ahí mismo.
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


positions = apply_solution(
                coordinates, delta=SEAM_DELTA, seam_reference=SEAM_REFERENCE
        )


# Visualizar capas
visualize_layers_3d(all_layers, layers_z)

# Generar todas las rutas de herramienta
toolpaths = generate_all_toolpaths(all_layers)

#Quitar # si se quiere ver la progresión de posiciones en un archivo HTML
# visualize_positions_progressive(positions, output_file="posiciones_progresivas.html", delay=50)

codigo_contornos(positions)