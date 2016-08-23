import os,sys
from HashFileLib import HashFile
from typofixer.keyboard import Keyboard
import Levenshtein as lv

module_path = os.path.dirname(os.path.abspath(__file__))

secretDir = "mySecretDir"
logPath = os.path.join(module_path,secretDir,"logFile.txt")
hashPath = os.path.join(module_path,secretDir,"hashFile.txt")
shortPath = os.path.join(module_path,secretDir,"shortTermFile.txt")
# lastSessPath = os.path.join(module_path,secretDir,"lastSessTime.txt")

logFile = HashFile(logPath)
shortFile = HashFile(shortPath)
longFile = HashFile(hashPath)

hashDataList = []

NO_HASH_IND = ""

# if we don't implement but just record there's
# no use to save the last sessionn's time
'''def didTimeOut:
    lastSessFile = HashFile(lastSessPath)
    data =  lastSessFile.getData()
    split = data.splitlines()
    if len(split) != 1:
        raise Exception("Wrong sess form")
    lastTime= split[0]
    currTime = lastSessFile.getStrTimeNow()
    return not lastSessFile.isSameSess(lastTime,currTime)
   '''
def isInHashList(typo):
    for hs,salt,ind in hashDataList:
        if hs == longFile.makeHash(typo,salt):
            #return ind
            return hs
    return NO_HASH_IND

if __name__ == "__main__":
    argList = sys.argv
    if len(argList) != 3:
        raise ValueError("wrong number of arguments")
    pswd =  argList[1]  # getting the pswd as an argument
    nowStr = argList[2] # getting the time as an argument
    
    # initializing file editors
    hashDataList = longFile.getListOfTuplesHashSalt()
    shortData = shortFile.getData()
    # initializing keyboard for press distances
    kb = Keyboard('US')
    
    for line in shortData.splitlines():
        split = line.split(',')
        if len(split) != 2:
            raise Exception("wrong short-file form")
        typo,timestamp = split 
        # ***************************
        #           MISSING
        # decrypting the typo,
        # maybe also decoding it if in hex
        
        typo_press = kb.word_to_key_presses(typo)
        pswd_press = kb.word_to_key_presses(pswd)
        dist = lv.distance(typo_press,pswd_press)

        #*****************************
        #           MISSING
        # information about the old typo-fixers-
        # whether it would have worked
        
        typo_ind = isInHashList(typo)
        if typo_ind == NO_HASH_IND: # a new typo
            hs,salt = longFile.getHashAndNewSalt(typo)
            #longFile.addHashLine(hs,salt,dist) # add to cach
            longFile.addHashLine(hs,salt)
            # Takiing into considerations:
            # if we check for every typo , the moment we get it
            # whether it's in the cach already - the cach needs to store
            # the distance
            # otherwise - there's no need for that
            # ALSO:
            # if we always compare first to the cach
            # we can use a random int ID
            typo_ind = hs # setting the hash form as the ID 
            
        # adding to log
        logFile.addLogLine(str(typo_ind),timestamp,dist,"typo")

    # logging that the pswd was recieved
    logFile.addLogLine("0",nowStr,0,"real pswd")
    
    # if changing it into an implementations -
    # there's a need to add session time recording

    # deleting the tmp short cach
    shortFile.cleanFile()
    

        
        
    
        
