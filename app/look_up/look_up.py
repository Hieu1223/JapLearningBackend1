from jamdict import Jamdict
jam = Jamdict()

def look_up(word:str):
    return jam.lookup(word)