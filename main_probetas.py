from patterns.translate_KRL import KRLTranslator
from probetas_path import probeta_path
from visualizadores import visualize_path_3d
from probetas_path import cuadrado
from probetas_path import probeta_path_z_vertical

# Ajuste para la firma actual: probeta_path usa step_y en lugar de step_x
positions = probeta_path(x=200, y=200, z=2.5, step_y=2.3, step_z=2.5, offset_z=2.5)  #x,y,z,step_y,step_z,offset_z
#positions = cuadrado(x=250, y=250, offset_z=2.5)
#positions = probeta_path_z_vertical(x=150, y=0, z=20, step_z=1.65, offset_z=1.6) #x,y,z,step_x,step_z
# Visualizar la ruta de puntos en 3D interactiva
visualize_path_3d(positions)

def codigo_probetas(poses, vent = 1,temp = 200, speed = 0.045 ):

        filename_export = "traccionfinal"

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
 
        for i, capa in enumerate(poses):
                print(f"Procesando capa {i}: {capa}")
                krl.add_line_to_src_file("LIN {X " + str(capa[0][0]) + ", Y " + str(capa[0][1]) + ", Z " + str(
                        capa[0][2]+5) + ", A " + str(0) + ", B " + str(90) + ", C " + str(0) + "} C_DIS\n")
                krl.add_line_to_src_file("WAIT SEC 1 \n")
                krl.add_line_to_src_file("$OUT[1] = TRUE \n")

                for pose in capa:
                        krl.add_line_to_src_file("LIN {X " + str(pose[0]) + ", Y " + str(pose[1]) + ", Z " + str(
                                pose[2]) + ", A " + str(0) + ", B " + str(90) + ", C " + str(0) + "} C_DIS\n")
                        
                krl.add_line_to_src_file("$OUT[1] = FALSE \n")
                krl.add_line_to_src_file("\n")
                krl.add_line_to_src_file(";Wait for \n")
                krl.add_line_to_src_file("; END POSITION FOR \n")
        
        print(f"Archivo KRL generado: {filename_export}.src")
codigo_probetas(positions)
