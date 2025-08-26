# __author__ = 'Ulises Campodonico'
# __email__ = 'ulises.campodonico@ug.uchile.cl'

class KRLTranslator:

    def __init__(self, file_name, axis_vel=[10,10,10,10,10,10], home_vel=10, speed_ms = 0.05):
        self.file_name = file_name
        self.src_file = None
        self.dat_file = None
        self.axis_vel = axis_vel
        self.home_vel = home_vel
        self.speed_ms = speed_ms

    # function to translate a circle to KRL syntax
    def CIRC_KRL(self, START, AUX, END, CA):
        # the start point is where the robot is
        # $POS_ACT
        # all the points are frame variables
        # check if the points are frame variables
        CIRC = "CIRC {0}, {1}, {2}".format(AUX, END, CA)
        return CIRC

    # function to translate a linear pattern to KRL syntax
    def LIN_KRL(self, START, END):
        # the start point is where the robot is
        # $POS_ACT
        # all the points are frame variables
        # check if the points are frame variables
        LIN = "LIN {0} C_DIS".format(END)
        return LIN

    # function to translate a point to point move KRL syntax
    def PTP_KRL(self, END):
        # the start point is where the robot is
        # $POS_ACT
        # all the points are frame variables
        # check if the points are frame variables
        PTP = "PTP {0}".format(END)
        return PTP
    
    def sleep(self, time):
        return "WAIT SEC {}\n".format(time)

    def HOME_FOLD(self):
        if self.src_file:
            self.src_file.write(";HOME\n")
            self.src_file.write(";FOLD PTP HOME Vel={}% DEFAULT\n".format(self.home_vel))
            self.src_file.write("$BWDSTART=FALSE\n")
            self.src_file.write("$H_POS=XHOME\n")
            self.src_file.write("PDAT_ACT=PDEFAULT\n")
            self.src_file.write("FDAT_ACT=FHOME\n")
            self.src_file.write("BAS(#PTP_DAT )\n")
            self.src_file.write("BAS (#VEL_PTP,{} )\n".format(self.home_vel))
            self.src_file.write("PTP XHOME\n")
            self.src_file.write(";ENDFOLD\n")
        else:
            return "SRC file is not open."

    def INI_FOLD_DAT(self,name="test"):
        #previous lines
        self.dat_file.write("&ACCESS RVP \n")
        self.dat_file.write("&PARAM TEMPLATE = C:\\KRC\\Roboter\\Template\\vorgabe \n")
        self.dat_file.write("&PARAM EDITMASK = * \n")
        self.dat_file.write("DEFDAT {}( ) \n".format(name))
        #load ini dat
        ini_file = open("kuka_KRL_setup/ini_dat.txt", "r")
        lines = ini_file.readlines()
        self.src_file.writelines(lines)
        ini_file.close()

    def INI_FOLD(self,name="test"):

        #previous lines
        self.src_file.write("&ACCESS RVP \n")
        self.src_file.write("&PARAM TEMPLATE = C:\\KRC\\Roboter\\Template\\vorgabe \n")
        self.src_file.write("&PARAM EDITMASK = * \n")
        self.src_file.write("DEF {}( ) \n".format(name))
        #load ini text for src file from txt file and write it to the src file
        #open ini file
        ini_file = open("kuka_KRL_setup/ini_src.txt", "r")
        #read the lines
        lines = ini_file.readlines()
        #append the lines to the src file
        self.src_file.writelines(lines)
        #close the ini file
        ini_file.close()
        

    def SET_VEL_AXIS(self):
        if self.src_file:
            self.src_file.write("\n")
            self.src_file.write("; SPEED PTP FOR AXIS\n")
            for i, vel in enumerate(self.axis_vel):
                self.src_file.write(f"$VEL_AXIS[{i + 1}] = {vel}\n")
        else:
            return "SRC file is not open."

    # function to create the .src and .dat files
    def create_KRL_file(self):
        self.src_file = open(self.file_name + ".src", "w")
        self.INI_FOLD(name=self.file_name)
        self.SET_VEL_AXIS()
        self.src_file.write(";SMOOTHNESS\n")
        self.src_file.write("$APO.CDIS = 2\n")
        self.src_file.write(";ADVANCE\n")
        self.src_file.write("$ADVANCE = 3\n")
        self.src_file.write(";SET TOOL AND BASE\n")
        self.src_file.write("$TOOL = TOOL_DATA[3]\n")
        self.src_file.write("$BASE = BASE_DATA[2]\n")
        self.HOME_FOLD()
        self.src_file.write(";USER PROGRAM\n")
        self.src_file.write(";SPEED $VEL.CP\n")
        self.src_file.write("$VEL.CP={}\n".format(self.speed_ms))
        self.src_file.write(";END USER CODE\n")
        self.HOME_FOLD()
        self.src_file.write("END\n")
        self.src_file.close()
        dat_file = open(self.file_name + ".dat", "w")
        dat_file.write("DEFDAT " + self.file_name + "()\n")
        dat_file.write("ENDDAT\n")
        dat_file.close()
        return "CREATE KRL FILES"

    # function to add a line to the .src file
    def add_line_to_src_file(self, add_line):
        # open file in edit mode
        # Read the file and store its content
        #close file if it was open
        if self.src_file:
            self.src_file.close()
        src_file = open(self.file_name+".src", "r")
        lines = src_file.readlines()
        # Search for "END\n" line
        for i, line in enumerate(lines):
            if line.strip() == ';END USER CODE':
                lines.insert(i, add_line)
                break

        file_w = open(self.file_name+".src", "w")
        file_w.writelines(lines)

        return "ADD LINE TO SRC FILE"

    # function to add a line to the .dat file
    def create_variables(self, type, name, filename):
        #TODO: add the variables to the .dat file

        return "CREATE VARIABLES"
