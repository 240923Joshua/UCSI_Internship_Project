from argon2 import PasswordHasher

def hash_password(password):
    ph = PasswordHasher()
    return ph.hash(password)

def verify_password(stored_hash, provided_password):
    ph = PasswordHasher()
    try:
        ph.verify(stored_hash, provided_password)
        return True
    except:
        return False
