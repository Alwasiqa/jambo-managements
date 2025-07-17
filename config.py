"""
Configuration settings for Flask application
"""
import os

class Config:
    """Base configuration"""
    SECRET_KEY = 'jambo-management-secret-key-2025'
    DEBUG = True
    DATABASE = os.path.join(os.path.dirname(__file__), 'jambo_simple.db')
    
    # Debug database path
    print(f"🗄️ Database path: {DATABASE}")
    print(f"🗄️ Database exists: {os.path.exists(DATABASE)}")
    if os.path.exists(DATABASE):
        print(f"🗄️ Database size: {os.path.getsize(DATABASE)} bytes")
    
    # PDF settings
    try:
        from reportlab.lib.pagesizes import letter, A4
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False
    
    # Application settings
    DEBUG = True 