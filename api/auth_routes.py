# api/auth_routes.py
# User authentication and authorization

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

# User database file (simple JSON storage for MVP)
USERS_FILE = "/home/radxa/efio/users.json"

# Default users (created on first run)
DEFAULT_USERS = {
    "admin": {
        "username": "admin",
        "password_hash": bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "admin",
        "email": "admin@edgeforce.local",
        "full_name": "Administrator"
    },
    "operator": {
        "username": "operator",
        "password_hash": bcrypt.hashpw("operator123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "operator",
        "email": "operator@edgeforce.local",
        "full_name": "Operator User"
    }
}

# ============================================
# User Database Functions
# ============================================

def load_users():
    """Load users from JSON file"""
    if not os.path.exists(USERS_FILE):
        # Create default users on first run
        save_users(DEFAULT_USERS)
        print("✅ Created default users: admin/admin123, operator/operator123")
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
        return jsonify({
            "error": "Username and password required"
        }), 400
    
    # Get user from database
    user = get_user(username)
    
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({
            "error": "Invalid username or password"
        }), 401
    
    # Create JWT tokens
    access_token = create_access_token(
        identity=username,
        additional_claims={
            "role": user['role'],
            "email": user.get('email', ''),
            "full_name": user.get('full_name', username)
        },
        expires_delta=timedelta(hours=8)
    )
    
    refresh_token = create_refresh_token(
        identity=username,
        expires_delta=timedelta(days=30)
    )
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": username,
            "role": user['role'],
            "email": user.get('email', ''),
            "full_name": user.get('full_name', username)
        }
    }), 200

@auth_api.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user = get_jwt_identity()
    user = get_user(current_user)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    access_token = create_access_token(
        identity=current_user,
        additional_claims={
            "role": user['role'],
            "email": user.get('email', ''),
            "full_name": user.get('full_name', current_user)
        },
        expires_delta=timedelta(hours=8)
    )
    
    return jsonify({
        "access_token": access_token
    }), 200

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
        "full_name": claims.get('full_name')
    }), 200

@auth_api.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout (client should delete token)"""
    # In a production system, you'd add token to blacklist
    return jsonify({
        "message": "Logged out successfully"
    }), 200

# ============================================
# User Management Endpoints (Admin Only)
# ============================================

def admin_required():
    """Check if current user is admin"""
    claims = get_jwt()
    return claims.get('role') == 'admin'

@auth_api.route('/api/users', methods=['GET'])
@jwt_required()
def list_users():
    """List all users (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    users = load_users()
    # Remove password hashes from response
    user_list = []
    for username, user_data in users.items():
        user_list.append({
            "username": username,
            "role": user_data['role'],
            "email": user_data.get('email', ''),
            "full_name": user_data.get('full_name', username)
        })
    
    return jsonify({"users": user_list}), 200

@auth_api.route('/api/users', methods=['POST'])
@jwt_required()
def create_user():
    """Create new user (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'operator')
    email = data.get('email', '')
    full_name = data.get('full_name', username)
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    if role not in ['admin', 'operator', 'viewer']:
        return jsonify({"error": "Invalid role"}), 400
    
    users = load_users()
    
    if username in users:
        return jsonify({"error": "Username already exists"}), 409
    
    # Create password hash
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Add user
    users[username] = {
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "email": email,
        "full_name": full_name
    }
    
    if save_users(users):
        return jsonify({
            "message": "User created successfully",
            "user": {
                "username": username,
                "role": role,
                "email": email,
                "full_name": full_name
            }
        }), 201
    else:
        return jsonify({"error": "Failed to save user"}), 500

@auth_api.route('/api/users/<username>', methods=['DELETE'])
@jwt_required()
def delete_user(username):
    """Delete user (admin only)"""
    if not admin_required():
        return jsonify({"error": "Admin access required"}), 403
    
    current_user = get_jwt_identity()
    
    if username == current_user:
        return jsonify({"error": "Cannot delete yourself"}), 400
    
    users = load_users()
    
    if username not in users:
        return jsonify({"error": "User not found"}), 404
    
    del users[username]
    
    if save_users(users):
        return jsonify({"message": "User deleted successfully"}), 200
    else:
        return jsonify({"error": "Failed to delete user"}), 500

@auth_api.route('/api/users/<username>/password', methods=['PUT'])
@jwt_required()
def change_password(username):
    """Change user password"""
    current_user = get_jwt_identity()
    is_admin = admin_required()
    
    # Users can change their own password, admins can change anyone's
    if username != current_user and not is_admin:
        return jsonify({"error": "Access denied"}), 403
    
    data = request.get_json()
    new_password = data.get('new_password')
    old_password = data.get('old_password')  # Required if changing own password
    
    if not new_password:
        return jsonify({"error": "New password required"}), 400
    
    users = load_users()
    
    if username not in users:
        return jsonify({"error": "User not found"}), 404
    
    # If user is changing their own password, verify old password
    if username == current_user and not is_admin:
        if not old_password or not verify_password(old_password, users[username]['password_hash']):
            return jsonify({"error": "Invalid old password"}), 401
    
    # Update password
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    users[username]['password_hash'] = password_hash
    
    if save_users(users):
        return jsonify({"message": "Password changed successfully"}), 200
    else:
        return jsonify({"error": "Failed to change password"}), 500