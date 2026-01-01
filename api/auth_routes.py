# api/auth_routes.py
# UPDATED: Force password change on first login

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
import bcrypt
import json
import os
from datetime import timedelta

auth_api = Blueprint('auth_api', __name__)

# User database file
USERS_FILE = "/home/radxa/efio/users.json"

# UPDATED: Default users now require password change
DEFAULT_USERS = {
    "admin": {
        "username": "admin",
        "password_hash": bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "admin",
        "email": "admin@edgeforce.local",
        "full_name": "Administrator",
        "force_password_change": True,  # NEW: Require change
        "created_at": None
    },
    "operator": {
        "username": "operator",
        "password_hash": bcrypt.hashpw("operator123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "operator",
        "email": "operator@edgeforce.local",
        "full_name": "Operator User",
        "force_password_change": True,  # NEW: Require change
        "created_at": None
    }
}

def load_users():
    """Load users from JSON file"""
    if not os.path.exists(USERS_FILE):
        save_users(DEFAULT_USERS)
        print("⚠️  WARNING: Default users created - CHANGE PASSWORDS IMMEDIATELY!")
        return DEFAULT_USERS
    
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading users: {e}")
        return DEFAULT_USERS

def save_users(users):
    """Save users to JSON file"""
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error saving users: {e}")
        return False

def get_user(username):
    """Get user by username"""
    users = load_users()
    return users.get(username)

def verify_password(password, password_hash):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

# ============================================
# Authentication Endpoints
# ============================================

@auth_api.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    user = get_user(username)
    
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({"error": "Invalid username or password"}), 401
    
    # Check if password change is required
    force_change = user.get('force_password_change', False)
    
    # Create JWT tokens
    additional_claims = {
        "role": user['role'],
        "email": user.get('email', ''),
        "full_name": user.get('full_name', username),
        "force_password_change": force_change  # NEW: Include in token
    }
    
    access_token = create_access_token(
        identity=username,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=8)
    )
    
    refresh_token = create_refresh_token(
        identity=username,
        expires_delta=timedelta(days=30)
    )
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "force_password_change": force_change,  # NEW: Tell frontend
        "user": {
            "username": username,
            "role": user['role'],
            "email": user.get('email', ''),
            "full_name": user.get('full_name', username)
        }
    }), 200

@auth_api.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password - works for both forced and voluntary changes"""
    current_user = get_jwt_identity()
    claims = get_jwt()
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not new_password:
        return jsonify({"error": "New password required"}), 400
    
    # Validate new password strength
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    
    users = load_users()
    user = users.get(current_user)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # For forced password changes, allow without current password verification
    force_change = claims.get('force_password_change', False)
    
    if not force_change:
        # Normal password change - verify current password
        if not current_password or not verify_password(current_password, user['password_hash']):
            return jsonify({"error": "Current password incorrect"}), 401
    
    # Update password
    user['password_hash'] = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user['force_password_change'] = False  # Clear flag
    
    users[current_user] = user
    
    if save_users(users):
        # Issue new token without force_password_change flag
        new_token = create_access_token(
            identity=current_user,
            additional_claims={
                "role": user['role'],
                "email": user.get('email', ''),
                "full_name": user.get('full_name', current_user),
                "force_password_change": False
            },
            expires_delta=timedelta(hours=8)
        )
        
        return jsonify({
            "message": "Password changed successfully",
            "access_token": new_token
        }), 200
    else:
        return jsonify({"error": "Failed to save password"}), 500

@auth_api.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user = get_jwt_identity()
    user = get_user(current_user)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Include current force_password_change status
    force_change = user.get('force_password_change', False)
    
    access_token = create_access_token(
        identity=current_user,
        additional_claims={
            "role": user['role'],
            "email": user.get('email', ''),
            "full_name": user.get('full_name', current_user),
            "force_password_change": force_change
        },
        expires_delta=timedelta(hours=8)
    )
    
    return jsonify({"access_token": access_token}), 200

@auth_api.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info"""
    current_user = get_jwt_identity()
    claims = get_jwt()
    
    return jsonify({
        "username": current_user,
        "role": claims.get('role'),
        "email": claims.get('email'),
        "full_name": claims.get('full_name'),
        "force_password_change": claims.get('force_password_change', False)
    }), 200

@auth_api.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout"""
    return jsonify({"message": "Logged out successfully"}), 200

# [Rest of the file remains the same - user management endpoints]