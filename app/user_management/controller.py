from sqlmodel import Session
from .schema import RegisterRequest
from ..database.user import User
from ..security.auth import hash_password
from ..database.security.queries import create_user_auth
from fastapi.exceptions import HTTPException

class UserController:
    @staticmethod
    def register_user(session: Session, data: RegisterRequest) -> User:
        # 1. Create the Profile
        # display_name defaults to username if not provided
        new_user = User(
            display_name=data.display_name or data.username
        )
        session.add(new_user)
        
        # Flush to grab the ID without committing the transaction yet
        session.flush()

        # 2. Link Auth Credentials
        # This calls your 'create_user_auth' query
        try:
            
            
            create_user_auth(
                session=session,
                user_id=new_user.id,
                username=data.username,
                hashed_pass=hash_password(data.password)
            )
        except Exception:
            session.rollback()
            raise HTTPException(status_code=400, detail="Username already taken")

        # 3. Final commit for both tables
        session.commit()
        session.refresh(new_user)
        return new_user