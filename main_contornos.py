from patterns.translate_KRL import KRLTranslator
from probetas_path import probeta_path
from visualizadores import visualize_path_3d
from slicer import coordenadas_stl
from visualizadores import visualize_layers_3d
from visualizadores import visualize_toolpaths_3d
from slicer import generate_all_toolpaths

stl = "cono.stl"
altura_capa = 1.6
z_offset = 1.6

def codigo_contornos(poses, vent = 1,temp = 200, speed = 0.03):

        filename_export = "biglemur"

        krl = KRLTranslator(filename_export, axis_vel=[
                        15, 15, 15, 15, 15, 15], speed_ms=speed)
        krl.create_KRL_file()

        RPM = int(speed * 1000)  # Convertir a RPM (ejemplo: vent=1 -> 1000 RPM)

        #Señales de salida para activar la temperatura y el ventilador
        krl.add_line_to_src_file("; OUT[TEMP] = " + str(temp) + " \n")
        krl.add_line_to_src_file("; OUT[vent] = " + str(vent) + " \n")
        krl.add_line_to_src_file("; OUT[RPM] = " + str(RPM) + " \n")

        krl.add_line_to_src_file("; USER POSES CALLS \n")
        # TODO: Call the first pose from setup config and save a new json file with the new starting pose
        krl.add_line_to_src_file("PTP {X 75, Y 30, Z 420, A 0, B 90, C 0} \n") #COI
        krl.add_line_to_src_file("; USER POSES CALLS \n")


        krl.add_line_to_src_file("LIN {X " + str(poses[0][0][0][0]) + ", Y " + str(poses[0][0][0][1]) + ", Z " + str(
                                poses[0][0][0][2]+5) + ", A " + str(0) + ", B " + str(90) + ", C " + str(0) + "} C_DIS\n")
        krl.add_line_to_src_file("WAIT SEC 1 \n")
        krl.add_line_to_src_file("$OUT[1] = TRUE \n")
        krl.add_line_to_src_file("WAIT SEC 2 \n")
 
        for i, capa in enumerate(poses):
                for j, contour in enumerate(capa):
                        #print(f"Procesando capa {i}, contorno {j}: {contour}")
                        krl.add_line_to_src_file("LIN {X " + str(contour[0][0]) + ", Y " + str(contour[0][1]) + ", Z " + str(
                                contour[0][2]) + ", A " + str(0) + ", B " + str(90) + ", C " + str(0) + "} C_DIS\n")

                        for pose in contour:
                                krl.add_line_to_src_file("LIN {X " + str(pose[0]) + ", Y " + str(pose[1]) + ", Z " + str(
                                        pose[2]) + ", A " + str(0) + ", B " + str(90) + ", C " + str(0) + "} C_DIS\n")
                                
        krl.add_line_to_src_file("$OUT[1] = FALSE \n")
        krl.add_line_to_src_file("\n")
        krl.add_line_to_src_file(";Wait for \n")
        krl.add_line_to_src_file("; END POSITION FOR \n")
        
        print(f"Archivo KRL generado: {filename_export}.src")

coordinates, all_layers, layers_z = coordenadas_stl(stl, altura_capa, z_offset)
positions = coordinates

# Visualizar capas
visualize_layers_3d(all_layers, layers_z)

# Generar todas las rutas de herramienta
toolpaths = generate_all_toolpaths(all_layers)

# Visualizar las rutas de herramienta
visualize_toolpaths_3d(toolpaths, layers_z)

codigo_contornos(positions)

