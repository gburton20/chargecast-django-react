import jwt
import requests
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions
import os

class Auth0JSONWebTokenAuthentication(authentication.BaseAuthentication):
    """
    Authenticate against Auth0 JWT tokens
    """
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
            
        parts = auth_header.split()
        
        if parts[0].lower() != 'bearer':
            return None
            
        if len(parts) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header')
        elif len(parts) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header')
            
        token = parts[1]
        return self._authenticate_credentials(token)
    
    def _authenticate_credentials(self, token):
        try:
            # Decode and verify the JWT token
            payload = self._decode_jwt(token)
            
            # Get or create user from Auth0 sub (subject)
            auth0_user_id = payload.get('sub')
            email = payload.get('email', f'{auth0_user_id}@auth0.user')
            
            user, created = User.objects.get_or_create(
                username=auth0_user_id,
                defaults={'email': email}
            )
            
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))
    
    def _decode_jwt(self, token):
        # Get Auth0 public key
        jwks_url = f'https://{os.getenv("AUTH0_DOMAIN")}/.well-known/jwks.json'
        jwks = requests.get(jwks_url).json()
        
        # Decode token (simplified - in production use proper key validation)
        unverified_header = jwt.get_unverified_header(token)
        
        # Verify and decode
        payload = jwt.decode(
            token,
            jwks,
            algorithms=['RS256'],
            audience=os.getenv('AUTH0_API_IDENTIFIER'),
            issuer=f'https://{os.getenv("AUTH0_DOMAIN")}/'
        )
        
        return payload