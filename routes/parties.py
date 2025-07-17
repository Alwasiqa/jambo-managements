"""
Parties management routes
"""
from flask import Blueprint, render_template, request, jsonify
from database import get_db_connection
from datetime import datetime

bp = Blueprint('parties', __name__)

@bp.route('/')
def list_parties():
    """List all parties"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, party_type, phone, email, city, is_active
            FROM parties
            ORDER BY name
        """)
        
        parties = []
        for row in cursor.fetchall():
            parties.append({
                'id': row[0],
                'name': row[1],
                'party_type': row[2] if row[2] else '',
                'phone': row[3],
                'email': row[4],
                'city': row[5],
                'is_active': row[6]
            })
        
        return render_template('parties.html', parties=parties)
        
    except Exception as e:
        print(f"Error listing parties: {e}")
        return render_template('parties.html', parties=[])
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/update-type', methods=['POST'])
def update_party_type():
    """Update party type"""
    try:
        data = request.get_json()
        party_id = data.get('party_id')
        party_type = data.get('party_type')
        
        if not party_id or not party_type:
            return jsonify({
                'success': False,
                'message': 'Party ID and type are required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First get the party name
        cursor.execute("SELECT name FROM parties WHERE id = ?", (party_id,))
        party = cursor.fetchone()
        if not party:
            return jsonify({
                'success': False,
                'message': 'Party not found'
            })
            
        party_name = party[0]
        
        # Update party type
        cursor.execute("""
            UPDATE parties
            SET party_type = ?
            WHERE id = ?
        """, (party_type, party_id))
        
        # Also update any matching names in jambo_rolls table
        if party_type == 'supplier':
            cursor.execute("""
                UPDATE parties
                SET party_type = 'supplier'
                WHERE name = ?
            """, (party_name,))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Party type updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating party type: {e}")
        return jsonify({
            'success': False,
            'message': f'Error updating party type: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/update-status', methods=['POST'])
def update_party_status():
    """Update party active status"""
    try:
        data = request.get_json()
        party_id = data.get('party_id')
        is_active = data.get('is_active')
        
        if party_id is None or is_active is None:
            return jsonify({
                'success': False,
                'message': 'Party ID and status are required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE parties
            SET is_active = ?
            WHERE id = ?
        """, (1 if is_active else 0, party_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Party status updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating party status: {e}")
        return jsonify({
            'success': False,
            'message': f'Error updating party status: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/edit/<int:party_id>', methods=['GET'])
def get_party(party_id):
    """Get party details for editing"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, party_type, phone, email, address, city
            FROM parties
            WHERE id = ?
        """, (party_id,))
        
        party = cursor.fetchone()
        
        if not party:
            return jsonify({
                'success': False,
                'message': 'Party not found'
            })
            
        return jsonify({
            'success': True,
            'party': {
                'id': party[0],
                'name': party[1],
                'party_type': party[2],
                'phone': party[3],
                'email': party[4],
                'address': party[5],
                'city': party[6]
            }
        })
        
    except Exception as e:
        print(f"Error getting party: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting party: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/save', methods=['POST'])
def save_party():
    """Save party (create or update)"""
    try:
        data = request.get_json()
        party_id = data.get('id')
        name = data.get('name', '').strip()
        party_type = data.get('party_type', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        address = data.get('address', '').strip()
        city = data.get('city', '').strip()
        
        if not name or not party_type:
            return jsonify({
                'success': False,
                'message': 'Name and type are required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if party_id:  # Update existing
            cursor.execute("""
                UPDATE parties
                SET name = ?, party_type = ?, phone = ?, email = ?, address = ?, city = ?
                WHERE id = ?
            """, (name, party_type, phone, email, address, city, party_id))
        else:  # Create new
            cursor.execute("""
                INSERT INTO parties (name, party_type, phone, email, address, city, created_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (name, party_type, phone, email, address, city, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Party {"updated" if party_id else "created"} successfully'
        })
        
    except Exception as e:
        print(f"Error saving party: {e}")
        return jsonify({
            'success': False,
            'message': f'Error saving party: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/delete/<int:party_id>', methods=['POST'])
def delete_party(party_id):
    """Delete party"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if party is used in jambo_rolls
        cursor.execute("SELECT COUNT(*) FROM jambo_rolls WHERE party_name = (SELECT name FROM parties WHERE id = ?)", (party_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({
                'success': False,
                'message': 'Cannot delete party as it is used in jambo rolls. You can deactivate it instead.'
            })
        
        cursor.execute("DELETE FROM parties WHERE id = ?", (party_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Party deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting party: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting party: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/customers')
def get_customers():
    """Get customers list for dropdown"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get customers from parties table
        cursor.execute("""
            SELECT DISTINCT name 
            FROM parties 
            WHERE party_type = 'customer' 
            AND is_active = 1 
            AND name IS NOT NULL 
            AND name != ''
            ORDER BY name
        """)
        
        customers = [row[0] for row in cursor.fetchall()]
        
        # Also get unique customer names from customer_orders table
        cursor.execute("""
            SELECT DISTINCT customer_name 
            FROM customer_orders 
            WHERE customer_name IS NOT NULL 
            AND customer_name != ''
            ORDER BY customer_name
        """)
        
        existing_customers = [row[0] for row in cursor.fetchall()]
        
        # Combine both lists and remove duplicates
        all_customers = list(set(customers + existing_customers))
        all_customers.sort()
        
        return jsonify({
            'success': True,
            'customers': all_customers
        })
        
    except Exception as e:
        print(f"Error getting customers: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting customers: {e}',
            'customers': []
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/customers/add', methods=['POST'])
def add_customer():
    """Add new customer"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        address = data.get('address', '').strip()
        city = data.get('city', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'Customer name is required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if customer already exists
        cursor.execute("SELECT id FROM parties WHERE name = ?", (name,))
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Customer already exists'
            })
        
        # Add new customer
        cursor.execute("""
            INSERT INTO parties (
                name, party_type, phone, email, address, city, 
                created_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            name, 'customer', phone, email, address, city,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer added successfully'
        })
        
    except Exception as e:
        print(f"Error adding customer: {e}")
        return jsonify({
            'success': False,
            'message': f'Error adding customer: {e}'
        })
        
    finally:
        if conn:
            conn.close() 