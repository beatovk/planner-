#!/usr/bin/env python3
"""
Script to create a superuser for the Entertainment Planner API
"""
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from apps.core.db import engine, SessionLocal
from apps.core.models import User
from apps.core.auth import get_password_hash
from apps.core.config import settings


def create_superuser():
    """Create a superuser if it doesn't exist"""
    db = SessionLocal()
    try:
        # Check if superuser already exists
        existing_user = db.query(User).filter(
            (User.username == settings.admin_username) | 
            (User.email == settings.admin_email)
        ).first()
        
        if existing_user:
            print(f"Superuser with username '{settings.admin_username}' or email '{settings.admin_email}' already exists!")
            return
        
        # Create superuser
        hashed_password = get_password_hash(settings.admin_password)
        superuser = User(
            username=settings.admin_username,
            email=settings.admin_email,
            hashed_password=hashed_password,
            is_superuser=True,
            is_active=True
        )
        
        db.add(superuser)
        db.commit()
        
        print(f"Superuser '{settings.admin_username}' created successfully!")
        print(f"Username: {settings.admin_username}")
        print(f"Email: {settings.admin_email}")
        print(f"Password: {settings.admin_password}")
        
    except Exception as e:
        print(f"Error creating superuser: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_superuser()
