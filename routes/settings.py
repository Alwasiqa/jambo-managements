"""
Settings and user management routes
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import get_db_connection
from datetime import datetime
import hashlib
from functools import wraps
from auth_utils import login_required

bp = Blueprint('settings', __name__)

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed

@bp.route('/')
@login_required
def settings_dashboard():
    """Settings dashboard page"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get users count
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        total_users = cursor.fetchone()[0] or 0
        
        # Get admin users count
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1")
        admin_users = cursor.fetchone()[0] or 0
        
        # Get recent users
        cursor.execute("""
            SELECT id, username, full_name, email, role, created_date, last_login
            FROM users 
            WHERE is_active = 1
            ORDER BY created_date DESC 
            LIMIT 5
        """)
        recent_users = cursor.fetchall()
        
        # Convert to list of dicts
        users_list = []
        for user in recent_users:
            users_list.append({
                'id': user[0],
                'username': user[1],
                'full_name': user[2],
                'email': user[3] or '-',
                'role': user[4],
                'created_date': user[5],
                'last_login': user[6] or '-'
            })
        
        conn.close()
        
        return render_template('settings.html',
                             total_users=total_users,
                             admin_users=admin_users,
                             recent_users=users_list)
                             
    except Exception as e:
        print(f"Settings error: {e}")
        if 'conn' in locals():
            conn.close()
        return render_template('settings.html',
                             total_users=0,
                             admin_users=0,
                             recent_users=[])

@bp.route('/users')
@login_required
def list_users():
    """List all users"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, full_name, email, role, is_active, created_date, last_login
            FROM users
            ORDER BY created_date DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3] or '-',
                'role': row[4],
                'is_active': row[5],
                'created_date': row[6],
                'last_login': row[7] or '-'
            })
        
        return render_template('users_list.html', users=users)
        
    except Exception as e:
        print(f"Error listing users: {e}")
        return render_template('users_list.html', users=[])
        
    finally:
        if conn:
            conn.close()

@bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """Add new user"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            role = request.form.get('role', 'user')
            
            if not username or not password or not full_name:
                return jsonify({'success': False, 'message': 'Username, password aur full name required hain'})
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
            if cursor.fetchone()[0] > 0:
                return jsonify({'success': False, 'message': 'Username already exists'})
            
            # Hash password
            hashed_password = hash_password(password)
            
            # Insert new user
            cursor.execute('''
                INSERT INTO users (username, password, full_name, email, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, hashed_password, full_name, email, role))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'User successfully created'})
            
        except Exception as e:
            print(f"Error adding user: {e}")
            return jsonify({'success': False, 'message': f'Error creating user: {e}'})
    
    return render_template('add_user.html')

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Edit existing user"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if request.method == 'POST':
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            role = request.form.get('role')
            is_active = request.form.get('is_active', 0)
            new_password = request.form.get('new_password')
            
            if not full_name:
                return jsonify({'success': False, 'message': 'Full name required hai'})
            
            # Update user
            if new_password:
                hashed_password = hash_password(new_password)
                cursor.execute('''
                    UPDATE users 
                    SET full_name = ?, email = ?, role = ?, is_active = ?, password = ?
                    WHERE id = ?
                ''', (full_name, email, role, is_active, hashed_password, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET full_name = ?, email = ?, role = ?, is_active = ?
                    WHERE id = ?
                ''', (full_name, email, role, is_active, user_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'User successfully updated'})
        
        # GET request - show edit form
        cursor.execute('SELECT id, username, full_name, email, role, is_active FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return redirect(url_for('settings.list_users'))
        
        user_data = {
            'id': user[0],
            'username': user[1],
            'full_name': user[2],
            'email': user[3] or '',
            'role': user[4],
            'is_active': user[5]
        }
        
        conn.close()
        return render_template('edit_user.html', user=user_data)
        
    except Exception as e:
        print(f"Error editing user: {e}")
        return redirect(url_for('settings.list_users'))

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete user (soft delete)"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Soft delete - set is_active to 0
        cursor.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'User successfully deleted'})
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({'success': False, 'message': f'Error deleting user: {e}'})

@bp.route('/api/users')
@login_required
def get_users_api():
    """API endpoint to get users list"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, full_name, email, role, is_active, created_date
            FROM users
            WHERE is_active = 1
            ORDER BY created_date DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3] or '',
                'role': row[4],
                'is_active': row[5],
                'created_date': row[6]
            })
        
        return jsonify({'success': True, 'users': users})
        
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({'success': False, 'message': f'Error getting users: {e}'})
        
    finally:
        if conn:
            conn.close() 