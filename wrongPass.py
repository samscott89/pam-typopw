# MY CHANGE
from HashFileLib import HashFile
import os
import sys


module_path = os.path.dirname(os.path.abspath(__file__))

secretDir = "mySecretDir"
logPath = os.path.join(module_path,secretDir,"logFile.txt")
hashPath = os.path.join(module_path,secretDir,"hashFile.txt")
shortPath = os.path.join(module_path,secretDir,"shortTermFile.txt")
# lastSess = os.path.join(module_path,secretDir,"lastSessTime.txt")
                        
if __name__ == "__main__":

    argList = sys.argv
    if len(argList) != 2:
        raise ValueError()
    shortFile = HashFile(shortPath)
    #lastSessFile = HashFile(lastSess)
    typo = argList[1]
    nowStr = shortFile.getStrTimeNow()
    # ************************
    # MISSING
    # encryption and encoding of the typo
    # ************************
    shortFile.addLine(typo+','+nowStr)

    # lastSessFile.cleanFile()
    # lastSessFile.addLine(nowStr)

    
    
