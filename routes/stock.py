"""
Stock Management Routes
"""
from flask import Blueprint, render_template, request, jsonify
from database import get_db_connection
from datetime import datetime

bp = Blueprint('stock', __name__)

@bp.route('/manage')
def manage_stock():
    """Stock management page"""
    return render_template('stock_manage.html')

@bp.route('/api/items', methods=['GET'])
def get_stock_items():
    """Get all stock items"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, size_mm, size_yard, color, brand, micron, packing, created_date, is_active
            FROM stock_items
            ORDER BY created_date DESC
        """)
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'size_mm': row[1],
                'size_yard': row[2],
                'color': row[3],
                'brand': row[4],
                'micron': row[5],
                'packing': row[6] or 72,
                'created_date': row[7],
                'is_active': bool(row[8])
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@bp.route('/api/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    """Ek item ki details la kar bheje (Edit modal ke liye)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, size_mm, size_yard, color, brand, micron, packing
            FROM stock_items
            WHERE id = ?
        """, (item_id,))
        row = cursor.fetchone()
        print("DEBUG row:", row)  # Debug print
        conn.close()
        if row:
            return jsonify({
                'success': True,
                'item': {
                    'id': row[0],
                    'size_mm': row[1],
                    'size_yard': row[2],
                    'color': row[3],
                    'brand': row[4],
                    'micron': row[5],
                    'packing': str(row[6]) if row[6] is not None else '72'
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Item not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/create', methods=['POST'])
def create_stock_item():
    """Manually create stock item"""
    try:
        data = request.get_json()
        
        size_mm = data.get('size_mm')
        size_yard = data.get('size_yard')
        color = data.get('color')
        brand = data.get('brand')
        micron = data.get('micron')
        # Packing ko int me convert karo, blank aaye to 72 save karo
        packing = int(data.get('packing', 72) or 72)
        
        # Validation
        if not all([size_mm, size_yard, color, brand, micron]):
            return jsonify({
                'success': False,
                'message': 'Sabhi fields zaroori hain: Size MM, Size Yard, Color, Brand, Micron'
            })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if item already exists
        cursor.execute("""
            SELECT id FROM stock_items 
            WHERE size_mm = ? AND size_yard = ? AND color = ? AND brand = ? AND micron = ?
        """, (size_mm, size_yard, color, brand, micron))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Ye item pehle se maujood hai!'
            })
        
        # Create new item
        cursor.execute("""
            INSERT INTO stock_items (size_mm, size_yard, color, brand, micron, packing)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (size_mm, size_yard, color, brand, micron, packing))
        
        item_id = cursor.lastrowid
        
        # Add initial stock transaction (manual entry)
        cursor.execute("""
            INSERT INTO stock_transactions (
                item_id, transaction_date, transaction_type, quantity, reference_id
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            item_id,
            datetime.now().strftime('%Y-%m-%d'),
            'manual_entry',
            0,  # Initial quantity 0
            f'MANUAL-{item_id}'
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Stock item successfully create ho gaya! ID: {item_id}',
            'item_id': item_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating stock item: {str(e)}'
        })

@bp.route('/api/update/<int:item_id>', methods=['PUT'])
def update_stock_item(item_id):
    """Update stock item (ab packing bhi update hogi)"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()
        # Packing ko int me convert karo, blank aaye to 72 save karo
        packing = int(data.get('packing', 72) or 72)
        cursor.execute("""
            UPDATE stock_items 
            SET size_mm = ?, size_yard = ?, color = ?, brand = ?, micron = ?, packing = ?
            WHERE id = ?
        """, (
            data.get('size_mm'),
            data.get('size_yard'),
            data.get('color'),
            data.get('brand'),
            data.get('micron'),
            packing,
            item_id
        ))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Item nahi mila!'
            })
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': 'Stock item successfully update ho gaya!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error updating stock item: {str(e)}'
        })

@bp.route('/api/delete/<int:item_id>', methods=['DELETE'])
def delete_stock_item(item_id):
    """Delete stock item (only if no transactions)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if item has any transactions
        cursor.execute("""
            SELECT COUNT(*) FROM stock_transactions WHERE item_id = ?
        """, (item_id,))
        
        transaction_count = cursor.fetchone()[0]
        
        if transaction_count > 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Ye item delete nahi ho sakta kyunki {transaction_count} transactions hain!'
            })
        
        # Delete item
        cursor.execute("DELETE FROM stock_items WHERE id = ?", (item_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Item nahi mila!'
            })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Stock item successfully delete ho gaya!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting stock item: {str(e)}'
        })

@bp.route('/api/transactions/<int:item_id>')
def get_item_transactions(item_id):
    """Get transactions for specific item"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT st.transaction_date, st.transaction_type, st.quantity, st.reference_id,
                   si.size_mm, si.size_yard, si.color, si.brand, si.micron
            FROM stock_transactions st
            JOIN stock_items si ON st.item_id = si.id
            WHERE st.item_id = ?
            ORDER BY st.transaction_date DESC
        """, (item_id,))
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                'date': row[0],
                'type': row[1],
                'quantity': row[2],
                'reference': row[3],
                'description': f"{row[4]}mm x {row[5]} Yard {row[6]} {row[7]} {row[8]}mic"
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'transactions': transactions
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }) 