from patterns.translate_KRL import KRLTranslator
from visualizadores import visualize_path_3d
from slicer import coordenadas_stl
from visualizadores import visualize_layers_3d
from visualizadores import visualize_positions_progressive
from slicer import generate_all_toolpaths

stl = "Geometrías_contornos/lampsb.stl"
altura_capa = 2
z_offset =0

def codigo_contornos(poses, vent=1, temp=200, vel=0.035, t_enf = 2, t_retracción = 0.25):

        filename = "lampsbfv"
        filename_export = "Archivos_KRL/Contorno_KRL/" 


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

                # --- Separación entre capas ---
                # Movimiento elevado (Z+5) al punto de inicio de la capa,
                # con la extrusión apagada, igual que en main_probetas.py
                krl.add_line_to_src_file("LIN {X " + str(primer_punto[0]) + ", Y " + str(primer_punto[1]) + ", Z " + str(
                        primer_punto[2] + 5) + ", A 0, B 90, C 0} C_DIS\n")
                krl.add_line_to_src_file("WAIT SEC " + str(t_enf) + "\n")
                krl.add_line_to_src_file("$OUT[1] = TRUE \n")
                krl.add_line_to_src_file("WAIT SEC " + str(t_retracción) + "\n")
                

                for j, contour in enumerate(capa):
                        # Bajada al inicio del contorno (a su Z real, sin offset)
                        krl.add_line_to_src_file("LIN {X " + str(contour[0][0]) + ", Y " + str(contour[0][1]) + ", Z " + str(
                                contour[0][2]) + ", A 0, B 90, C 0} C_DIS\n")

                        for pose in contour:
                                krl.add_line_to_src_file("LIN {X " + str(pose[0]) + ", Y " + str(pose[1]) + ", Z " + str(
                                        pose[2]) + ", A 0, B 90, C 0} C_DIS\n")

                # Apagar extrusión al terminar la capa, antes de subir a la siguiente
                krl.add_line_to_src_file("$OUT[1] = FALSE \n")
                krl.add_line_to_src_file("\n")
                krl.add_line_to_src_file("; END LAYER " + str(i) + " \n")

        print(f"Archivo KRL generado: {filename_export}{filename}.src")

coordinates, all_layers, layers_z = coordenadas_stl(stl, altura_capa, z_offset)
positions = coordinates

# Visualizar capas
visualize_layers_3d(all_layers, layers_z)

# Generar todas las rutas de herramienta
toolpaths = generate_all_toolpaths(all_layers)

#visualize_positions_progressive(positions, output_file="posiciones_progresivas.html", delay=50)

codigo_contornos(positions)

