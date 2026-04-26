from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from .auth import hash_password, verify_password, create_token
from ..database import SessionDep
from ..database.security.queries import get_auth_user_by_username
from .auth import CurrentUser

router = APIRouter()

@router.post("/token")
def login(session: SessionDep, form: OAuth2PasswordRequestForm = Depends()):
    # Call the specific auth query
    auth_entry = get_auth_user_by_username(session, form.username)
    
    if not auth_entry or not verify_password(form.password, auth_entry.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # Generate token using the linked Profile user_id
    token = create_token(auth_entry.user_id)
    return {"access_token": token, "token_type": "bearer"}
