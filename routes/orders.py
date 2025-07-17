"""
Orders management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db_connection
from datetime import datetime

bp = Blueprint('orders', __name__)

def format_date(date_str):
    """Convert date to DD-MM-YYYY format"""
    try:
        if not date_str:
            return ''
        # Try different date formats
        for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y']:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime('%d-%m-%Y')
            except ValueError:
                continue
        return date_str  # Return original if no format matches
    except:
        return date_str

@bp.route('/orders')
def list_orders():
    """Orders listing with items count"""
    try:
        search = request.args.get('search', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get orders with items count
        if search:
            cursor.execute('''
                SELECT co.*, COUNT(oi.item_id) as item_count,
                       COALESCE(SUM(oi.amount), 0) as total_amount
                FROM customer_orders co
                LEFT JOIN order_items oi ON co.order_no = oi.order_no
                WHERE CAST(co.order_no AS TEXT) LIKE ? 
                   OR LOWER(co.customer_name) LIKE LOWER(?) 
                   OR co.customer_phone LIKE ?
                GROUP BY co.id, co.order_no, co.order_date, co.customer_name, 
                         co.customer_phone, co.customer_address, co.status
                ORDER BY co.order_date DESC
            ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cursor.execute('''
                SELECT co.*, COUNT(oi.item_id) as item_count,
                       COALESCE(SUM(oi.amount), 0) as total_amount
                FROM customer_orders co
                LEFT JOIN order_items oi ON co.order_no = oi.order_no
                GROUP BY co.id, co.order_no, co.order_date, co.customer_name, 
                         co.customer_phone, co.customer_address, co.status
                ORDER BY co.order_date DESC
            ''')
        
        orders = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts with proper column mapping
        orders_list = []
        for order in orders:
            orders_list.append({
                'id': order[0],
                'order_no': order[1],
                'order_date': format_date(order[2]) if order[2] else '',
                'customer_name': order[3] or '',
                'customer_phone': order[4] or '',
                'customer_address': order[5] or '',
                'status': order[6] or 'Pending',
                'total_amount': float(order[7] or 0),
                'item_count': int(order[8] or 0)
            })
        
        return render_template('simple_orders.html', 
                             orders=orders_list,
                             search=search)
        
    except Exception as e:
        print(f"Error listing orders: {e}")
        return render_template('simple_orders.html',
                             orders=[],
                             search='')

@bp.route('/orders/add', methods=['GET', 'POST'])
def add_order():
    """Add new order with items"""
    if request.method == 'POST':
        try:
            # Order header info
            order_no = request.form['order_no']  # OR-XXXX format
            order_date = request.form['order_date']
            customer_name = request.form['customer_name']
            customer_phone = request.form.get('customer_phone', '')
            customer_address = request.form.get('customer_address', '')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            total_amount = 0
            item_count = 0
            
            # Process order items
            form_data = request.form.to_dict()
            items = {}
            
            # Parse items from form data
            for key, value in form_data.items():
                if key.startswith('items[') and '][' in key:
                    # Extract item number and field name
                    item_start = key.find('[') + 1
                    item_end = key.find(']')
                    field_start = key.find('][') + 2
                    field_end = key.rfind(']')
                    
                    if item_start > 0 and item_end > item_start and field_start > 0 and field_end > field_start:
                        item_num = key[item_start:item_end]
                        field_name = key[field_start:field_end]
                        
                        if item_num not in items:
                            items[item_num] = {}
                        items[item_num][field_name] = value
            
            # Insert order header first
            cursor.execute('''
                INSERT INTO customer_orders (order_no, order_date, customer_name, customer_phone, customer_address, status, total_amount)
                VALUES (?, ?, ?, ?, ?, 'Pending', ?)
            ''', (order_no, order_date, customer_name, customer_phone, customer_address, 0))
            
            # Insert order items
            for item_num, item_data in items.items():
                if item_data.get('size') and item_data.get('qty'):  # Only add items with basic data
                    size = item_data.get('size', '')
                    size_mm = int(item_data.get('size_mm', 0)) if item_data.get('size_mm') else None
                    size_yard = int(item_data.get('size_yard', 0)) if item_data.get('size_yard') else None
                    qty_text = item_data.get('qty', '')  # Keep as text
                    micron = int(item_data.get('micron', 37))
                    brand = item_data.get('brand', '')
                    colour = item_data.get('colour', '')
                    variety = item_data.get('variety', '')
                    packing = item_data.get('packing', '')
                    printed_matter = item_data.get('printed_matter', '')
                    unit_price = float(item_data.get('unit_price') or 0)
                    amount = float(item_data.get('amount') or 0)
                    notes = item_data.get('notes', '')
                    
                    cursor.execute('''
                        INSERT INTO order_items (order_no, size, size_mm, size_yard, qty, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (order_no, size, size_mm, size_yard, qty_text, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes))
                    
                    total_amount += amount
                    item_count += 1
            
            # Update order total amount
            cursor.execute('UPDATE customer_orders SET total_amount = ? WHERE order_no = ?', (total_amount, order_no))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Order {order_no} with {item_count} items added successfully! Total: Rs. {total_amount:,.0f}',
                'order_no': order_no
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    return render_template('simple_add_order.html')

@bp.route('/orders/details/<order_no>')
def order_details(order_no):
    """Order details page with complete information"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get order details
        cursor.execute('SELECT * FROM customer_orders WHERE order_no = ?', (order_no,))
        order = cursor.fetchone()
        
        if not order:
            return jsonify({
                'success': False,
                'error': f'Order {order_no} not found'
            })
        
        # Get order items with enhanced details
        cursor.execute('''
            SELECT item_id, order_no, size, qty, micron, brand, colour, variety, packing, 
                   printed_matter, unit_price, amount, notes
            FROM order_items 
            WHERE order_no = ?
            ORDER BY item_id
        ''', (order_no,))
        items = cursor.fetchall()
        
        # Convert to list of dicts
        items_list = []
        total_amount = 0
        
        for item in items:
            # Check if item is closed
            cursor.execute('SELECT closed_date, closed_reason FROM closed_order_items WHERE order_no = ? AND item_id = ?', (order_no, item[0]))
            closed_status = cursor.fetchone()
            
            # Format size display
            size_display = item[2] or '-'
            if item[2] and 'mm' in item[2] and 'Yard' in item[2]:
                # Already in correct format
                size_display = item[2]
            elif item[2]:
                # Try to parse and format
                try:
                    if 'mm' in item[2] and 'x' in item[2]:
                        size_display = item[2]
                    else:
                        size_display = item[2]
                except:
                    size_display = item[2]
            
            item_dict = {
                'item_id': item[0],
                'order_no': item[1],
                'size': size_display,
                'qty': item[3] or '-',
                'micron': item[4] or 37,
                'brand': item[5] or 'Brand',
                'colour': item[6] or 'Clear',
                'variety': item[7] or 'Type',
                'packing': item[8] or '48',
                'printed_matter': item[9] or '',
                'unit_price': item[10] or 0,
                'amount': item[11] or 0,
                'notes': item[12] or '',
                'is_closed': closed_status is not None,
                'closed_date': closed_status[0] if closed_status else None,
                'closed_reason': closed_status[1] if closed_status else None,
                'status': 'CLOSED' if closed_status else 'ACTIVE'
            }
            
            # Calculate required pieces
            qty_str = str(item_dict['qty']).lower()
            if 'ctn' in qty_str or 'carton' in qty_str:
                import re
                carton_match = re.search(r'(\d+)', qty_str)
                cartons = int(carton_match.group(1)) if carton_match else 1
                packing_qty = int(item_dict['packing']) if str(item_dict['packing']).isdigit() else 48
                required_pieces = cartons * packing_qty
                item_dict['required_pieces'] = required_pieces
                item_dict['cartons'] = cartons
                item_dict['pieces_per_carton'] = packing_qty
            else:
                item_dict['required_pieces'] = 0
                item_dict['cartons'] = 0
                item_dict['pieces_per_carton'] = 0
            
            items_list.append(item_dict)
            total_amount += float(item_dict['amount'])
        
        # Prepare order data
        order_data = {
            'id': order[0],
            'order_no': order[1],
            'order_date': order[2],
            'customer_name': order[3],
            'customer_phone': order[4],
            'customer_address': order[5],
            'status': order[6],
            'total_amount': order[7] or total_amount
        }
        
        return render_template('order_details.html', 
                             order=order_data, 
                             items=items_list,
                             items_count=len(items_list))
        
    except Exception as e:
        print(f"Error loading order details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@bp.route('/orders/edit/<order_no>', methods=['GET', 'POST'])
def edit_order(order_no):
    """Edit existing order with items"""
    try:
        if request.method == 'POST':
            # Check if request is JSON
            if request.is_json:
                data = request.get_json()
                
                # Extract order data
                order_date = data.get('order_date')
                customer_name = data.get('customer_name')
                customer_phone = data.get('customer_phone', '')
                customer_address = data.get('customer_address', '')
                status = data.get('status', 'Pending')
                
                # Validate required fields
                if not order_date or not customer_name:
                    return jsonify({
                        'success': False,
                        'error': 'Order date and customer name are required'
                    })
                
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Update order header
                cursor.execute('''
                    UPDATE customer_orders 
                    SET order_date = ?, customer_name = ?, customer_phone = ?, 
                        customer_address = ?, status = ?
                    WHERE order_no = ?
                ''', (order_date, customer_name, customer_phone, customer_address, status, order_no))
                
                # Production wale items nikaal lo
                cursor.execute('''
                    SELECT oi.item_id, oi.size FROM order_items oi
                    INNER JOIN production_orders po ON oi.item_id = po.item_id AND oi.order_no = po.order_no
                    WHERE oi.order_no = ?
                ''', (order_no,))
                production_items = cursor.fetchall()
                production_item_ids = [item[0] for item in production_items]
                production_item_list = [f"Item {item[0]} ({item[1]})" for item in production_items]

                # Sab item_id jo POST data mein aaye hain, unki list banao
                posted_item_ids = [str(item_data.get('item_id')) for _, item_data in data.get('items', {}).items() if item_data.get('item_id')]

                # Delete sirf un items ko karo jo na POST data mein hain, na production mein hain
                if posted_item_ids or production_item_ids:
                    all_skip_ids = posted_item_ids + [str(pid) for pid in production_item_ids]
                    cursor.execute('DELETE FROM order_items WHERE order_no = ? AND item_id NOT IN (%s)' % ','.join(['?']*len(all_skip_ids)), [order_no]+all_skip_ids)
                else:
                    cursor.execute('DELETE FROM order_items WHERE order_no = ?', (order_no,))

                # Process updated order items
                items = data.get('items', {})
                total_amount = 0
                items_list = []
                for index, item_data in items.items():
                    items_list.append((int(index), item_data))
                items_list.sort(key=lambda x: x[0])

                # Insert ya update sirf un items ko karo jinki production nahi hui (ya naya item hai)
                for _, item_data in items_list:
                    item_id = item_data.get('item_id')
                    if item_id and str(item_id) in [str(pid) for pid in production_item_ids]:
                        continue  # Roman Urdu: Production wale item ko skip kar rahe hain
                    if item_data.get('size') and item_data.get('qty'):
                        size = item_data.get('size', '')
                        qty_text = item_data.get('qty', '')
                        micron = int(item_data.get('micron', 37))
                        brand = item_data.get('brand', '')
                        colour = item_data.get('colour', '')
                        variety = item_data.get('variety', '')
                        packing = item_data.get('packing', '')
                        printed_matter = item_data.get('printed_matter', '')
                        unit_price = float(item_data.get('unit_price') or 0)
                        amount = float(item_data.get('amount') or 0)
                        notes = item_data.get('notes', '')
                        if item_id and str(item_id) not in [str(pid) for pid in production_item_ids]:
                            # Agar item_id hai aur production nahi hui, to update karo
                            cursor.execute('''
                                UPDATE order_items SET size=?, qty=?, micron=?, brand=?, colour=?, variety=?, packing=?, printed_matter=?, unit_price=?, amount=?, notes=?
                                WHERE order_no=? AND item_id=?
                            ''', (size, qty_text, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes, order_no, item_id))
                        elif not item_id:
                            # Naya item insert karo
                            cursor.execute('''
                                INSERT INTO order_items (
                                    order_no, size, qty, micron, brand, colour, variety, 
                                    packing, printed_matter, unit_price, amount, notes
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (order_no, size, qty_text, micron, brand, colour, variety, 
                                  packing, printed_matter, unit_price, amount, notes))
                        total_amount += amount

                # Update order total amount
                cursor.execute('UPDATE customer_orders SET total_amount = ? WHERE order_no = ?', 
                             (total_amount, order_no))
                conn.commit()
                conn.close()

                msg = f'Order {order_no} updated successfully! Total: Rs. {total_amount:,.0f}'
                if production_item_list:
                    msg += f'\nNote: Production wale items edit nahi ho sakte: {", ".join(production_item_list)}'
                return jsonify({
                    'success': True,
                    'message': msg,
                    'order_no': order_no
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid request format. Expected JSON data.'
                })
            
        else:  # GET request
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get order details
            cursor.execute('SELECT * FROM customer_orders WHERE order_no = ?', (order_no,))
            order = cursor.fetchone()
            
            if not order:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': f'Order {order_no} not found'
                })
            
            # Get order items
            cursor.execute('''
                SELECT item_id, size, qty, micron, brand, colour, variety, 
                       packing, printed_matter, unit_price, amount, notes
                FROM order_items 
                WHERE order_no = ?
                ORDER BY item_id
            ''', (order_no,))
            items = cursor.fetchall()
            
            # Convert to list of dicts
            order_data = {
                'id': order[0],
                'order_no': order[1],
                'order_date': order[2] if order[2] else '',  # Keep YYYY-MM-DD format for HTML date input
                'order_date_display': format_date(order[2]) if order[2] else '',  # DD-MM-YYYY format for display
                'customer_name': order[3] or '',
                'customer_phone': order[4] or '',
                'customer_address': order[5] or '',
                'status': order[6] or 'Pending',
                'total_amount': float(order[7] or 0)
            }
            
            items_list = []
            for item in items:
                items_list.append({
                    'item_id': item[0],
                    'size': item[1] or '',
                    'qty': item[2] or '',
                    'micron': item[3] or 37,
                    'brand': item[4] or '',
                    'colour': item[5] or '',
                    'variety': item[6] or '',
                    'packing': item[7] or '48',
                    'printed_matter': item[8] or '',
                    'unit_price': float(item[9] or 0),
                    'amount': float(item[10] or 0),
                    'notes': item[11] or ''
                })
            
            conn.close()
            
            return render_template('edit_order.html', 
                                 order=order_data,
                                 items=items_list)
            
    except Exception as e:
        print(f"Error editing order: {e}")
        return jsonify({
            'success': False,
            'error': f'Error editing order: {str(e)}'
        })

@bp.route('/orders/delete/<order_no>', methods=['POST', 'DELETE'])
def delete_order(order_no):
    """Delete order and its items"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete order items first
        cursor.execute('DELETE FROM order_items WHERE order_no = ?', (order_no,))
        
        # Delete order
        cursor.execute('DELETE FROM customer_orders WHERE order_no = ?', (order_no,))
        
        conn.commit()
        conn.close()
        
        flash(f'Order {order_no} deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting order: {str(e)}', 'error')
    
    return redirect(url_for('orders.orders'))

@bp.route('/orders/excel-import')
def orders_excel_import_page():
    """Excel import page for orders"""
    return render_template('orders_excel_import.html')

@bp.route('/generate_bill/<order_no>')
def generate_bill(order_no):
    """Roman Urdu: Bill generate karne ka route, ab order_no string hai"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get order details
        cursor.execute("""
            SELECT o.order_no, o.order_date, o.customer_name,
                   i.qty, i.size, i.colour, i.brand, i.mic,
                   i.printed, i.variety, i.per_ctn_qty, i.rate
            FROM customer_orders o
            LEFT JOIN order_items i ON o.order_no = i.order_no
            WHERE o.order_no = ?
        """, (order_no,))
        
        rows = cursor.fetchall()
        if not rows:
            flash('Order not found', 'error')
            return redirect(url_for('orders.list_orders'))
            
        # Format bill data
        bill_data = {
            'customer_name': rows[0][2],
            'date': datetime.strptime(rows[0][1], '%Y-%m-%d').strftime('%d/%m/%Y'),
            'bill_no': str(rows[0][0]),
            'items': []
        }
        
        # Format items
        for row in rows:
            bill_data['items'].append({
                'qty': row[3],
                'size': row[4],
                'colour': row[5],
                'brand': row[6],
                'mic': row[7],
                'printed': row[8],
                'varity': row[9],
                'per_ctn_qty': row[10],
                'rate': row[11]
            })
            
        conn.close()
        return render_template('bill_format.html', bill=bill_data)
        
    except Exception as e:
        print(f"Bill generation error: {e}")
        if 'conn' in locals():
            conn.close()
        flash('Error generating bill', 'error')
        return redirect(url_for('orders.list_orders'))

# ==== ORDER APIs ====

@bp.route('/api/next-order-number')
def api_get_next_order_number():
    """Get next available order number"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the highest order number
        cursor.execute("SELECT order_no FROM customer_orders ORDER BY CAST(SUBSTR(order_no, 4) AS INTEGER) DESC LIMIT 1")
        result = cursor.fetchone()
        
        if result:
            # Extract number from OR-XXXX format
            current_num = int(result[0].split('-')[1])
            next_num = current_num + 1
        else:
            next_num = 1
        
        next_order_no = f"OR-{next_num:04d}"
        
        conn.close()
        
        return jsonify({'next_order_no': next_order_no})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/whatsapp/order/<order_no>')
def whatsapp_order(order_no):
    """Generate WhatsApp message for existing order"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get order details
        cursor.execute('SELECT * FROM customer_orders WHERE order_no = ?', (order_no,))
        order = cursor.fetchone()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Get order items
        cursor.execute('''
            SELECT size, qty, micron, brand, colour, variety, packing, printed_matter
            FROM order_items 
            WHERE order_no = ?
        ''', (order_no,))
        items = cursor.fetchall()
        conn.close()
        
        # Create WhatsApp message
        whatsapp_message = f"*Order No*  : {order[1]}\n"      # order_no
        whatsapp_message += f"*Date*  : {format_date(order[2])}\n"         # order_date
        whatsapp_message += f"*Party Name*  : {order[3]}\n"   # customer_name
        
        # Add items
        for i, item in enumerate(items, 1):
            whatsapp_message += f"\nItem No {i}\n"
            whatsapp_message += f"*SIZE*  : {item[0] or '-'}\n"
            whatsapp_message += f"*QTY*  : {item[1] or '-'}\n"
            whatsapp_message += f"*MIC*  : {item[2] or '37'}\n"
            whatsapp_message += f"*BRAND*  : {item[3] or 'Brand'}\n"
            whatsapp_message += f"*COLOUR*  : {item[4] or 'Clear'}\n"
            whatsapp_message += f"*VARITY*  : {item[5] or 'Type'}\n"
            whatsapp_message += f"*PACKING*  : {item[6] or 'Box/Carton'}\n"
            
            if item[7] and item[7].strip():
                whatsapp_message += f"*Printed Matter*  : {item[7]}\n"
        
        return jsonify({
            'message': whatsapp_message,
            'customer': order[3],    # customer_name
            'phone': order[4] or ''  # customer_phone
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/whatsapp/preview', methods=['POST'])
def whatsapp_preview():
    """Generate WhatsApp message for new order (before saving)"""
    try:
        data = request.json
        
        # Generate temporary order number
        temp_order_no = f"TEMP_{datetime.now().strftime('%H%M%S')}"
        
        # Create WhatsApp message
        whatsapp_message = f"*Order No*  : {temp_order_no}\n"
        whatsapp_message += f"*Date*  : {data.get('order_date', '')}\n"
        whatsapp_message += f"*Party Name*  : {data.get('customer_name', '')}\n"
        
        # Add items
        items = data.get('items', [])
        for i, item in enumerate(items, 1):
            if item.get('size') or item.get('qty'):  # Only add if has size or qty
                whatsapp_message += f"\nItem No {i}\n"
                whatsapp_message += f"*SIZE*  : {item.get('size', '-')}\n"
                whatsapp_message += f"*QTY*  : {item.get('qty', '-')}\n"
                whatsapp_message += f"*MIC*  : {item.get('mic', '37')}\n"
                whatsapp_message += f"*BRAND*  : {item.get('brand', 'Brand')}\n"
                whatsapp_message += f"*COLOUR*  : {item.get('colour', 'Clear')}\n"
                whatsapp_message += f"*VARITY*  : {item.get('variety', 'Type')}\n"
                whatsapp_message += f"*PACKING*  : {item.get('packing', 'Box/Carton')}\n"
                
                if item.get('printed_matter', '').strip():
                    whatsapp_message += f"*Printed Matter*  : {item['printed_matter']}\n"
        
        return jsonify({
            'message': whatsapp_message,
            'customer': data.get('customer_name', ''),
            'phone': data.get('phone', '')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/order-item/close', methods=['POST'])
def close_order_item():
    """Close specific order item (hide from production)"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        item_id = data.get('item_id')
        reason = data.get('reason', 'Manual Close')
        
        if not order_no or not item_id:
            return jsonify({
                'success': False,
                'error': 'Order number and item ID are required'
            })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if item exists
        cursor.execute('SELECT * FROM order_items WHERE item_id = ? AND order_no = ?', 
                      (item_id, order_no))
        item = cursor.fetchone()
        
        if not item:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item not found'
            })
        
        # Check if already closed
        cursor.execute('''
            SELECT COUNT(*) FROM closed_order_items 
            WHERE order_no = ? AND item_id = ?
        ''', (order_no, item_id))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item already closed'
            })
        
        # Check for production
        cursor.execute('''
            SELECT COUNT(*) FROM production_orders 
            WHERE order_no = ? AND item_id = ?
        ''', (order_no, item_id))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Cannot close item - Production already started'
            })
        
        # Close the item
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO closed_order_items (
                order_no, item_id, closed_date, closed_reason
            ) VALUES (?, ?, ?, ?)
        ''', (order_no, item_id, current_date, reason))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Item closed successfully',
            'order_no': order_no,
            'item_id': item_id,
            'status': 'CLOSED',
            'closed_date': current_date,
            'closed_reason': reason
        })
        
    except Exception as e:
        print(f"Error closing order item: {e}")
        return jsonify({
            'success': False,
            'error': f'Error closing item: {str(e)}'
        })

@bp.route('/api/order-item/reopen', methods=['POST'])
def reopen_order_item():
    """Reopen closed order item"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        item_id = data.get('item_id')
        
        if not order_no or not item_id:
            return jsonify({
                'success': False,
                'error': 'Order number and item ID are required'
            })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if item is closed
        cursor.execute('''
            SELECT closed_date, closed_reason 
            FROM closed_order_items 
            WHERE order_no = ? AND item_id = ?
        ''', (order_no, item_id))
        closed_item = cursor.fetchone()
        
        if not closed_item:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Item is not closed'
            })
        
        # Reopen the item
        cursor.execute('''
            DELETE FROM closed_order_items 
            WHERE order_no = ? AND item_id = ?
        ''', (order_no, item_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Item reopened successfully',
            'order_no': order_no,
            'item_id': item_id,
            'status': 'ACTIVE'
        })
        
    except Exception as e:
        print(f"Error reopening order item: {e}")
        return jsonify({
            'success': False,
            'error': f'Error reopening item: {str(e)}'
        })

@bp.route('/api/order-item/status/<order_no>/<int:item_id>')
def get_order_item_status(order_no, item_id):
    """Get order item status (ACTIVE/CLOSED)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if item is closed
        cursor.execute('''
            SELECT closed_date, closed_reason 
            FROM closed_order_items 
            WHERE order_no = ? AND item_id = ?
        ''', (order_no, item_id))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'order_no': order_no,
                'item_id': item_id,
                'status': 'CLOSED',
                'closed_date': result[0],
                'closed_reason': result[1]
            })
        else:
            return jsonify({
                'success': True,
                'order_no': order_no,
                'item_id': item_id,
                'status': 'ACTIVE'
            })
            
    except Exception as e:
        print(f"Error getting item status: {e}")
        return jsonify({
            'success': False,
            'error': f'Error getting item status: {str(e)}'
        })

@bp.route('/api/orders/excel-import', methods=['POST'])
def api_import_orders():
    """Import orders from Excel data"""
    try:
        data = request.get_json()
        if not data or 'rows' not in data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            })
            
        rows = data['rows']
        if not rows:
            return jsonify({
                'success': False,
                'error': 'No rows found in data'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get next order number
        cursor.execute("SELECT order_no FROM customer_orders ORDER BY CAST(SUBSTR(order_no, 4) AS INTEGER) DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            current_num = int(result[0].split('-')[1])
            next_num = current_num + 1
        else:
            next_num = 1
            
        # Group rows by customer name
        customer_orders = {}
        today = datetime.now().strftime('%Y-%m-%d')
        
        for row in rows:
            try:
                # Expected columns: Name, Size, QTY, Mic, Brand, Colour, Varity, Packing
                customer_name = row[2].strip()  # Name is 3rd column
                
                if customer_name not in customer_orders:
                    order_no = f"OR-{next_num:04d}"
                    next_num += 1
                    customer_orders[customer_name] = {
                        'order_no': order_no,
                        'order_date': today,
                        'items': []
                    }
                    
                # Add item to customer's order
                customer_orders[customer_name]['items'].append({
                    'size': row[3].strip(),  # Size
                    'qty': row[4].strip(),   # QTY
                    'micron': int(row[5]) if row[5] else 37,  # Mic
                    'brand': row[6].strip() if row[6] else '',  # Brand
                    'colour': row[7].strip() if row[7] else '',  # Colour
                    'variety': row[8].strip() if row[8] else '',  # Varity
                    'packing': row[9].strip() if row[9] else '48'  # Packing
                })
                
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
                
        # Save orders to database
        orders_saved = 0
        items_saved = 0
        
        for customer_name, order_data in customer_orders.items():
            try:
                # Insert order
                cursor.execute('''
                    INSERT INTO customer_orders (order_no, order_date, customer_name, status)
                    VALUES (?, ?, ?, 'Pending')
                ''', (order_data['order_no'], order_data['order_date'], customer_name))
                
                # Insert items
                for item in order_data['items']:
                    cursor.execute('''
                        INSERT INTO order_items (order_no, size, qty, micron, brand, colour, variety, packing)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        order_data['order_no'],
                        item['size'],
                        item['qty'],
                        item['micron'],
                        item['brand'],
                        item['colour'],
                        item['variety'],
                        item['packing']
                    ))
                    items_saved += 1
                    
                orders_saved += 1
                
            except Exception as e:
                print(f"Error saving order for {customer_name}: {e}")
                continue
                
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {orders_saved} orders with {items_saved} items!'
        })
        
    except Exception as e:
        print(f"Excel import error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }) 

@bp.route('/api/customers')
def get_customers():
    """Get list of all customers"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get only customers from parties table
        cursor.execute("""
            SELECT DISTINCT name 
            FROM parties 
            WHERE party_type = 'customer'  -- Only get customers
            AND is_active = 1 
            AND name IS NOT NULL 
            AND name != ''
            ORDER BY name
        """)
        
        customers = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'customers': customers
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

@bp.route('/api/customers/<name>')
def get_customer_details(name):
    """Get customer details by name"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT phone, email, address, city
            FROM parties
            WHERE name = ? AND party_type = 'customer'
        """, (name,))
        
        customer = cursor.fetchone()
        
        if customer:
            return jsonify({
                'success': True,
                'customer': {
                    'phone': customer[0],
                    'email': customer[1],
                    'address': customer[2],
                    'city': customer[3]
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Customer not found'
            })
            
    except Exception as e:
        print(f"Error getting customer details: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting customer details: {e}'
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

@bp.route('/api/orders/next-number')
def get_next_order_number():
    """Get next available order number"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get highest order number
        cursor.execute("""
            SELECT order_no 
            FROM customer_orders 
            WHERE order_no LIKE 'OR-%' 
            ORDER BY order_no DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        
        if result and result[0]:
            # Extract number from OR-XXXX format
            current_num = int(result[0].split('-')[1])
            next_num = current_num + 1
        else:
            next_num = 1
            
        # Format as OR-XXXX
        next_order = f"OR-{str(next_num).zfill(4)}"
        
        return jsonify({
            'success': True,
            'next_order_no': next_order
        })
        
    except Exception as e:
        print(f"Error getting next order number: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting next order number: {e}'
        })
        
    finally:
        if conn:
            conn.close() 

@bp.route('/api/orders/save', methods=['POST'])
def save_order():
    """Save order (create or update)"""
    try:
        data = request.get_json()
        order_no = data.get('order_no')
        order_date = data.get('order_date')
        customer_name = data.get('customer_name')
        customer_phone = data.get('customer_phone', '')
        customer_address = data.get('customer_address', '')
        items = data.get('items', [])
        
        if not all([order_no, order_date, customer_name]):
            return jsonify({
                'success': False,
                'message': 'Order number, date, and customer name are required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if order exists
        cursor.execute("SELECT id FROM customer_orders WHERE order_no = ?", (order_no,))
        existing_order = cursor.fetchone()
        
        if existing_order:
            # Update existing order
            cursor.execute('''
                UPDATE customer_orders 
                SET order_date = ?, customer_name = ?, customer_phone = ?, customer_address = ?
                WHERE order_no = ?
            ''', (order_date, customer_name, customer_phone, customer_address, order_no))
            
            # Delete existing items
            cursor.execute("DELETE FROM order_items WHERE order_no = ?", (order_no,))
        else:
            # Create new order
            cursor.execute('''
                INSERT INTO customer_orders (order_no, order_date, customer_name, customer_phone, customer_address, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
            ''', (order_no, order_date, customer_name, customer_phone, customer_address))
        
        # Add items
        total_amount = 0
        for item in items:
            if item.get('size') and item.get('qty'):
                size = item.get('size', '')
                size_mm = int(item.get('size_mm', 0)) if item.get('size_mm') else None
                size_yard = int(item.get('size_yard', 0)) if item.get('size_yard') else None
                qty = item.get('qty', '')
                micron = int(item.get('micron', 37))
                brand = item.get('brand', '')
                colour = item.get('colour', '')
                variety = item.get('variety', '')
                packing = item.get('packing', '')
                printed_matter = item.get('printed_matter', '')
                unit_price = float(item.get('unit_price') or 0)
                amount = float(item.get('amount') or 0)
                notes = item.get('notes', '')
                
                cursor.execute('''
                    INSERT INTO order_items (order_no, size, size_mm, size_yard, qty, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (order_no, size, size_mm, size_yard, qty, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes))
                
                total_amount += amount
        
        # Update order total
        cursor.execute('UPDATE customer_orders SET total_amount = ? WHERE order_no = ?', (total_amount, order_no))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Order {order_no} saved successfully! Total: Rs. {total_amount:,.0f}',
            'order_no': order_no,
            'total_amount': total_amount
        })
        
    except Exception as e:
        print(f"Error saving order: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error saving order: {str(e)}'
        }) 