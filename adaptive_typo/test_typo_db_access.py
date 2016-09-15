import os
import pwd
from adaptive_typo.typo_db_access import (
    UserTypoDB,
    DB_NAME,
    waitlistT,
    hashCacheT
)
from adaptive_typo.pw_pkcrypto import (
    encrypt, decrypt, derive_public_key,
    derive_secret_key, update_ctx, compute_id
) # TODO REMOVE


NN = 5

def get_username():
    return pwd.getpwuid(os.getuid()).pw_name

def DB_path():
    # TODO _ for some reason it does't work
    user = get_username()
    db = UserTypoDB(user)
    return db.get_DB_path(user)
    #return "/home/{}/{}.db".format(get_username(), DB_NAME)

def remove_DB():
    os.remove(DB_path())

def start_DB():
    remove_DB()
    db = UserTypoDB(get_username())
    db.init_typotoler(get_pw(), NN)
    return db

def test_login_settings():
    typoDB = start_DB()
    #db = typoDB.getDB()
    assert typoDB.is_allowed_login()
    typoDB.disallow_login()
    assert not typoDB.is_allowed_login()
    typoDB.allow_login()
    assert typoDB.is_allowed_login()
    
def test_added_to_hash(isStandAlone = True):
    # INCLUDE TYPOS OF t1,t3,t5
    typoDB = start_DB()
    typoDB.add_typo_to_waitlist(t_1())
    typoDB.add_typo_to_waitlist(t_1())
    typoDB.add_typo_to_waitlist(t_5())
    typoDB.add_typo_to_waitlist(t_3())
    assert len(typoDB.getDB()[waitlistT]) == 4
    typoDB.original_password_entered(get_pw())
    assert len(typoDB.getDB()[waitlistT]) == 0
    hash_t = typoDB.getDB()[hashCacheT]
    assert len(hash_t) == 2
    _, t1_h, isIn_t1 = typoDB.fetch_from_cache(t_1(), False, False)
    assert isIn_t1
    assert hash_t.count(H_typo=t1_h) == 1
    _, t5_h, isIn_t5 = typoDB.fetch_from_cache(t_5(), False, False)
    assert isIn_t5
    assert hash_t.count(H_typo=t5_h) == 1
    assert len(hash_t) == 2
    if isStandAlone:
        remove_DB()
    else:
        return typoDB

def test_alt_typo(isStandAlone = True):
    print "TEST ALT TYPO"
    typoDB = test_added_to_hash(False)
    hash_t = typoDB.getDB()[hashCacheT]
    assert len(hash_t) > 0
    count = len(hash_t)
    for ii in range(5):
        typoDB.add_typo_to_waitlist(t_4())
##    print "added 5 typos to waitlist"
    t1_sk, t1_h, isIn_t1 = typoDB.fetch_from_cache(t_1(), False, False)
    typo_hash_line = hash_t.find_one(H_typo=t1_h)
    assert typo_hash_line
    pk = typo_hash_line['pk']
    salt = typo_hash_line['salt']
    assert isIn_t1
    typoDB.update_hash_cache_by_waitlist(t1_h,t1_sk)
    assert len(hash_t) == count+1
    if isStandAlone:
        remove_DB()
    else:
        return typoDB

def test_many_entries(isStandAlone = True):
    print "TEST MANY ENTRIES"
    BIG = 60

    typoDB = start_DB()
    
    log_t = typoDB.getDB()['Log']
    hash_t = typoDB.getDB()['HashCache']
    wait_t = typoDB.getDB()['Waitlist']

    print "start log:{}".format(len(log_t))
    
    for typ in listOfOneDist(BIG):
        typoDB.add_typo_to_waitlist(typ)
    print "waitlist len:{}".format(len(wait_t))
    assert (len(wait_t) == BIG)
    typoDB.original_password_entered(get_pw())
    print "log len:{}".format(len(log_t))
    print "hash len:{}".format(len(hash_t))
    assert(len(log_t) == BIG+1 ) # plus the original password
    realIn = min(BIG, NN)
    assert (len(hash_t) == realIn)
    if isStandAlone:
        remove_DB()
    else:
        return typoDB
    
def test_repeated_pw_use(isStandAlone = True):
    typoDB = start_DB()

    BIG = 60
    
    for typ in listOfOneDist(BIG):
        typoDB.add_typo_to_waitlist(typ)
        typoDB.original_password_entered(get_pw())
    
    if isStandAlone:
        remove_DB()
    else:
        return typoDB

def test_some_more(isStandAlone = True):
    # in the end INCLUDE TYPOS:
    # 1,2,4,5
    typoDB = test_added_to_hash(False)
    hash_t = typoDB.getDB()['HashCache']
    # typo 1 and 5 already in
    typoDB.original_password_entered(get_pw())
    typoDB.fetch_from_cache(t_1())
    typoDB.original_password_entered(get_pw())
    typoDB.add_typo_to_waitlist(t_2())
    typoDB.original_password_entered(get_pw())
    t2_sk,t2_h_id,is_t2_in = typoDB.fetch_from_cache(t_1(),False,False)
    assert is_t2_in # only if caps lock is considered as 1 dist
    typoDB.add_typo_to_waitlist(t_4())
    typoDB.add_typo_to_waitlist(t_6()) # shouldn't enter
    typoDB.update_hash_cache_by_waitlist(t2_h_id,t2_sk)
    for aa in hash_t.all():
        print aa
    assert (len(hash_t) == 4) # typos 1,2,4,5
    
    if isStandAlone:
        remove_DB()
    else:
        return typoDB    

def test_cache_policy(isStandAlone = True):
    # might fail under extreamly low probabiliy
    # ********* VERY HEAVY ***************
    typoDB = test_some_more(False)
    # typoDB include typos 1,2,4,5
    hash_t = typoDB.getDB()['HashCache']
    BIG = 60
    assert BIG >= NN  # to make sure we're trying to add enough times

    t1_sk,t1_h_id,t1_is_in = typoDB.fetch_from_cache(t_1(),False,False)
    assert t1_is_in
##    count_
    REALLY_BIG = 
    count = 0
    for ii in range(REALLY_BIG):
        for typo in listOfOneDist(BIG):
            # while the typo isn't in the cach yet
            t_sk,t_h_id,typo_is_in = typoDB.fetch_from_cache(typo,False,False)
            #while not typoDB.fetch_from_cache(typo,False,False)[2]:
            print t_sk,t_h_id,typo_is_in
            while not typo_is_in:
                typoDB.add_typo_to_waitlist(typo)
                typoDB.original_password_entered(get_pw())
                count += 1
                t_sk,t_h_id,typo_is_in = typoDB.fetch_from_cache(typo,False,False)
                
    t1_sk,t1_h_id,t1_is_in = typoDB.fetch_from_cache(t_1(),False,False)
    assert not t1_is_in

    if isStandAlone:
        remove_DB()
    else:
        return typoDB

    
def get_pw():
    return 'GoldApp&3'

def t_1():
    # lower initial
    return 'goldApp&3' 

def t_2():
    # caps
    return 'gOLDaPP&3'

def t_3():
    # dropped char
    # reduce entropy too much
    return 'GoldApp3'

def t_4():
    # 1 edit distance
    return 'GoldApp&2'

def t_5():
    return 'GoldApp&35'

def t_6():
    # 2 edit dist
    return 'G0ldAppp&3'

def listOfOneDist(length):
    ll = []
    # using only lower letters
    # to avoid shift --> 2 edit dist
    # insert the new char between existing chars
    m = ord('a')
    M = ord('z') + 1 - m
    for ii in range(length):
        col = ii/M + 1
        newC = chr(ii%M + m)
        typo = get_pw()[:col]+newC+get_pw()[col:]
        ll.append(typo)
        
    return ll
    
    

# "main"
test_some_more()
