from fastapi import Depends
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='api/v1/auth/token')

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, 'SECRET', algorithms=['HS256'])
    return payload