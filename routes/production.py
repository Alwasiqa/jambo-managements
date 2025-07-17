"""
Production management routes
"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import get_db_connection
from datetime import datetime

bp = Blueprint('production', __name__)

def create_or_get_stock_item(cursor, size_mm, size_yard, color, brand, micron, packing=72):
    """Create or get stock item"""
    # Try to find existing item
    cursor.execute("""
        SELECT id 
        FROM stock_items 
        WHERE size_mm = ? 
        AND size_yard = ? 
        AND color = ? 
        AND brand = ? 
        AND micron = ?
    """, (size_mm, size_yard, color, brand, micron))
    
    result = cursor.fetchone()
    if result:
        return result[0]
        
    # Create new item with packing value
    cursor.execute("""
        INSERT INTO stock_items (
            size_mm, size_yard, color, brand, micron, packing
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (size_mm, size_yard, color, brand, micron, packing))
    
    return cursor.lastrowid

def add_stock_transaction(cursor, item_id, transaction_type, quantity, reference_id, transaction_date=None):
    """Add stock transaction"""
    if not transaction_date:
        transaction_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    cursor.execute("""
        INSERT INTO stock_transactions (
            item_id, transaction_date, transaction_type, 
            quantity, reference_id
        ) VALUES (?, ?, ?, ?, ?)
    """, (item_id, transaction_date, transaction_type, quantity, reference_id))

@bp.route('/production')
def production_dashboard():
    """Production dashboard"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active orders
        cursor.execute("""
            SELECT co.*, COUNT(oi.item_id) as items_count
            FROM customer_orders co
            LEFT JOIN order_items oi ON co.order_no = oi.order_no
            WHERE co.status IN ('Pending', 'In Progress')
            GROUP BY co.order_no
            ORDER BY co.order_date DESC
        """)
        orders = cursor.fetchall()
        
        # Get active jambos
        cursor.execute("""
            SELECT j.* 
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
            AND j.balance_yard > 0
            ORDER BY j.date DESC
        """)
        jambos = cursor.fetchall()
        
        # Convert to list of dicts
        orders_list = []
        for order in orders:
            orders_list.append({
                'order_no': order[1],
                'order_date': order[2],
                'customer_name': order[3],
                'status': order[6],
                'items_count': order[8]
            })
        
        jambos_list = []
        for jambo in jambos:
            jambos_list.append({
                'jambo_no': jambo[1],
                'date': jambo[2],
                'size': f"{jambo[3]}mm x {jambo[4]}m",
                'colour': jambo[5],
                'micron': jambo[6],
                'party_name': jambo[9],
                'balance_yard': jambo[14]
            })
        
        conn.close()
        
        return render_template('production.html',
                             orders=orders_list,
                             jambos=jambos_list)
        
    except Exception as e:
        print(f"Error in production dashboard: {e}")
        return render_template('production.html',
                             orders=[],
                             jambos=[])

@bp.route('/production/jambo')
def jambo_production():
    """Jambo production page"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active jambos
        cursor.execute("""
            SELECT j.* 
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
            AND j.balance_yard > 0
            ORDER BY j.date DESC
        """)
        jambos = cursor.fetchall()
        
        # Convert to list of dicts
        jambos_list = []
        for jambo in jambos:
            jambos_list.append({
                'jambo_no': jambo[1],
                'date': jambo[2],
                'size': f"{jambo[3]}mm x {jambo[4]}m",
                'colour': jambo[5],
                'micron': jambo[6],
                'party_name': jambo[9],
                'balance_yard': jambo[14]
            })
        
        conn.close()
        
        return render_template('jambo_production.html',
                             jambos=jambos_list)
                             
    except Exception as e:
        print(f"Error in jambo production: {e}")
        return render_template('jambo_production.html',
                             jambos=[])

@bp.route('/production/edit/<int:production_id>')
def edit_production_page(production_id):
    """Edit production entry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM production WHERE id = ?', (production_id,))
    production_entry = cursor.fetchone()
    
    if not production_entry:
        flash('Production entry not found', 'error')
        return redirect(url_for('production.production_dashboard'))
    
    conn.close()
    
    return render_template('edit_production.html', production=production_entry)

@bp.route('/api/production/execute', methods=['POST'])
def execute_production():
    """Execute production order"""
    try:
        data = request.get_json()
        order = data['order']
        item = data['item']
        jambo = data['jambo']
        results = data['results']
        
        print(f"🔍 DEBUG: Executing production for Order {order['order_no']}, Item {item['id']}, Jambo {jambo['jambo_no']}")
        print(f"🔍 DEBUG: Item data in execute: {item}")
        print(f"🔍 DEBUG: Available item keys: {list(item.keys())}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current used yards for this jambo
        cursor.execute("""
            SELECT COALESCE(SUM(yards_used), 0) as total_used
            FROM production_orders
            WHERE jambo_no = ?
        """, (jambo['jambo_no'],))
        current_used_yards = cursor.fetchone()[0] or 0
        
        # Calculate new production values
        shafts_used = results.get('shafts', 0)
        pieces_per_shaft = results.get('pieces_per_shaft', 0)
        yards_per_shaft = results.get('yards_per_shaft', 0)
        
        # Calculate totals
        total_pieces_produced = shafts_used * pieces_per_shaft
        total_yards = shafts_used * yards_per_shaft
        
        print(f"🔍 DEBUG: Production values - Shafts: {shafts_used}, Pieces/Shaft: {pieces_per_shaft}, Total Pieces: {total_pieces_produced}")
        print(f"🔍 DEBUG: Yards calculation - Yards/Shaft: {yards_per_shaft}, Total Yards: {total_yards}")
        print(f"🔍 DEBUG: Current Used Yards: {current_used_yards}, New Total Used: {current_used_yards + total_yards}")
        
        # Insert production order
        cursor.execute('''
            INSERT INTO production_orders (
                order_no, item_id, jambo_no, produced_pieces,
                production_date, shafts_used, yards_used, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order['order_no'],
            item['id'],
            jambo['jambo_no'],
            total_pieces_produced,
            datetime.now().strftime('%Y-%m-%d'),
            shafts_used,
            total_yards,
            'In Progress'
        ))
        
        # Roman Urdu: Stock transactions add karna
        size_parts = item['size'].lower().replace('yard', '').strip().split('x')
        size_mm = int(size_parts[0].strip().replace('mm', ''))
        size_yard = int(size_parts[1].strip()) if len(size_parts) > 1 else 0
        
        # Get packing value from item data, default to 72 if not available
        item_packing = int(item.get('packing', 72)) if item.get('packing') else 72
        
        item_id = create_or_get_stock_item(
            cursor,
            size_mm=size_mm,
            size_yard=size_yard,
            color=item.get('colour', item.get('color', '')),
            brand=item.get('brand', 'Unknown'),  # Safe access with default value
            micron=item.get('micron', item.get('mic', 0)),
            packing=item_packing  # Pass actual packing value from order
        )
        add_stock_transaction(
            cursor,
            item_id=item_id,
            transaction_type='production',
            quantity=total_pieces_produced,
            reference_id=str(order['order_no']),
            transaction_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Update jambo balance based on total used yards
        calculated_yard = jambo.get('calculated_yard', 0)
        new_total_used = current_used_yards + total_yards
        new_balance = max(0, calculated_yard - new_total_used)
        
        cursor.execute('''
            UPDATE jambo_rolls 
            SET balance_yard = ? 
            WHERE jambo_no = ?
        ''', (new_balance, jambo['jambo_no']))
        
        # Update order status
        cursor.execute('''
            UPDATE customer_orders 
            SET status = 'In Progress' 
            WHERE order_no = ?
        ''', (order['order_no'],))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Production started successfully',
            'details': {
                'order_no': order['order_no'],
                'item_id': item['id'],
                'jambo_no': jambo['jambo_no'],
                'shafts': shafts_used,
                'pieces': total_pieces_produced,
                'yards': total_yards,
                'new_balance': new_balance,
                'total_used': new_total_used
            }
        })
        
    except Exception as e:
        print(f"❌ ERROR in execute_production: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/production/calculate', methods=['POST'])
def calculate_production():
    """Calculate production requirements"""
    try:
        data = request.get_json()
        print(f"🔍 DEBUG: Received data: {data}")
        
        order = data['order']
        item = data['item']
        jambo = data['jambo']
        manual_shafts = data.get('manual_shafts', 0)
        manual_pieces_per_shaft = data.get('manual_pieces_per_shaft', 0)
        
        print(f"🔍 DEBUG: Calculating production for Order {order['order_no']}, Item {item['id']}, Jambo {jambo['jambo_no']}")
        print(f"🔍 DEBUG: Jambo data: {jambo}")
        print(f"🔍 DEBUG: Item data: {item}")
        
        # Extract dimensions
        import re
        
        # Extract item width and length from size
        size_parts = item['size'].split('x') if 'x' in item['size'] else [item['size']]
        width_match = re.search(r'(\d+)', size_parts[0])
        item_width = int(width_match.group(1)) if width_match else 0
        
        if len(size_parts) > 1:
            length_match = re.search(r'(\d+)', size_parts[1])
            item_length = int(length_match.group(1)) if length_match else 0
        else:
            item_length = 4000  # Default length
        
        # Extract required pieces from order quantity
        def extract_pieces_from_qty(qty, packing=48):
            """Extract required pieces from quantity string with actual packing value"""
            if not qty:
                return 0
            
            qty_str = str(qty).lower().strip()
            
            # If already in pieces format
            pieces_match = re.search(r'(\d+)\s*pcs', qty_str)
            if pieces_match:
                return int(pieces_match.group(1))
            
            # If in cartons/boxes format
            carton_match = re.search(r'(\d+)\s*(ctn|carton|cartons|box|boxes)', qty_str)
            if carton_match:
                cartons = int(carton_match.group(1))
                return cartons * packing  # Use actual packing from item data
            
            # If just a number (assume cartons)
            number_match = re.search(r'^(\d+)$', qty_str)
            if number_match:
                cartons = int(number_match.group(1))
                return cartons * packing  # Use actual packing from item data
            
            return 0
        
        # Get actual packing value from item data
        item_packing = int(item.get('packing', 48)) if item.get('packing') else 48
        
        # Use REMAINING pieces instead of complete order qty
        total_order_pieces = extract_pieces_from_qty(item.get('qty', 0), item_packing)  # Complete order
        remaining_pieces = item.get('remaining_pieces', total_order_pieces)  # Remaining balance
        
        # Use remaining pieces for shaft calculation
        required_pieces = remaining_pieces
        
        print(f"🔍 DEBUG: Total order: {total_order_pieces} pieces, Remaining: {remaining_pieces} pieces")
        
        # Jambo specifications
        jambo_width = jambo['size_mm']
        jambo_balance = jambo.get('balance_yard', 0)  # Use get() with default value
        jambo_extra = jambo.get('extra_yards', 0)
        
        print(f"🔍 DEBUG: Jambo specs - Width: {jambo_width}, Balance: {jambo_balance}, Extra: {jambo_extra}")
        
        # Calculate pieces per shaft - use manual override if provided
        auto_pieces_per_shaft = jambo_width // item_width if item_width > 0 else 1
        pieces_per_shaft = manual_pieces_per_shaft if manual_pieces_per_shaft > 0 else auto_pieces_per_shaft
        
        # AUTO-CALCULATE REQUIRED SHAFTS based on REMAINING pieces only
        if required_pieces > 0 and pieces_per_shaft > 0:
            auto_calculated_shafts = (required_pieces + pieces_per_shaft - 1) // pieces_per_shaft  # Ceiling division
        else:
            auto_calculated_shafts = 0  # No shafts needed if no remaining pieces
        
        # DETERMINE FINAL SHAFTS: Manual override or auto-calculated
        if manual_shafts > 0:
            final_shafts = manual_shafts  # Use manual override
            shafts_source = "Manual Override"
        else:
            final_shafts = auto_calculated_shafts  # Use auto-calculated
            shafts_source = "Auto-Calculated"
        
        # Production calculations using final shafts
        yards_per_shaft = item_length
        actual_pieces_produced = final_shafts * pieces_per_shaft
        total_yards_needed = final_shafts * yards_per_shaft
        efficiency = (item_width * pieces_per_shaft / jambo_width) * 100 if jambo_width > 0 else 0
        
        total_available = jambo_balance + jambo_extra
        using_extra = total_yards_needed > jambo_balance
        extra_needed = max(0, total_yards_needed - jambo_balance)
        remaining_after = total_available - total_yards_needed
        
        is_feasible = (final_shafts > 0 and total_yards_needed > 0 and total_yards_needed <= total_available)
        
        results = {
            'feasible': is_feasible,
            'shafts': final_shafts,  # Final shafts used (auto or manual)
            'auto_calculated_shafts': auto_calculated_shafts,  # Show what system calculated
            'shafts_source': shafts_source,  # Show if auto or manual
            'pieces_per_shaft': pieces_per_shaft,
            'yards_per_shaft': yards_per_shaft,
            'total_pieces': actual_pieces_produced,
            'required_pieces': required_pieces,  # REMAINING pieces
            'total_order_pieces': total_order_pieces,  # COMPLETE order
            'already_produced': total_order_pieces - remaining_pieces,  # Already produced
            'total_yards': total_yards_needed,
            'efficiency': efficiency,
            'jambo_width': jambo_width,
            'item_width': item_width,
            'jambo_balance': jambo_balance,
            'total_available': total_available,
            'using_extra': using_extra,
            'extra_needed': extra_needed,
            'remaining_after': remaining_after,
            'order_fulfillment': (min(100, actual_pieces_produced / required_pieces * 100)) if required_pieces > 0 else 100,
            'balance_fulfillment': (min(100, actual_pieces_produced / required_pieces * 100)) if required_pieces > 0 else 100  # Balance fulfillment
        }
        
        print(f"🔍 DEBUG: Calculation results: {results}")
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        print(f"❌ ERROR in calculate_production: {str(e)}")
        print(f"❌ DEBUG Data: {data}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/production/orders')
def get_production_orders():
    """Get active orders for production"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active orders (not closed)
        cursor.execute('''
            SELECT co.*, COUNT(oi.item_id) as item_count 
            FROM customer_orders co
            LEFT JOIN order_items oi ON co.order_no = oi.order_no
            WHERE co.status IN ('Pending', 'In Progress', 'Partial')
            GROUP BY co.order_no
            ORDER BY co.order_date DESC
        ''')
        
        orders = []
        for row in cursor.fetchall():
            orders.append({
                'order_no': row[1],
                'order_date': row[2],
                'customer_name': row[3],
                'status': row[6],
                'total_amount': row[7],
                'items_count': row[8]
            })
        
        conn.close()
        return jsonify({'success': True, 'orders': orders})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/production/order-items/<order_no>')
def get_order_items(order_no):
    """Get items for specific order with production balance"""
    try:
        print(f"🔍 DEBUG: Getting items for order: {order_no}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get order items with calculated production data - Added order_no and customer_name
        query = '''
            SELECT oi.item_id, oi.order_no, oi.size, oi.qty, oi.micron, oi.brand, oi.colour, 
                   oi.variety, oi.packing, oi.printed_matter, oi.unit_price, oi.amount, oi.notes,
                   co.customer_name,
                   COALESCE(SUM(po.produced_pieces), 0) as produced_pieces,
                   COALESCE(SUM(po.shafts_used), 0) as total_shafts
            FROM order_items oi
            LEFT JOIN customer_orders co ON oi.order_no = co.order_no
            LEFT JOIN closed_order_items coi ON oi.order_no = coi.order_no AND oi.item_id = coi.item_id
            LEFT JOIN production_orders po ON oi.order_no = po.order_no AND oi.item_id = po.item_id
            WHERE oi.order_no = ?
            AND coi.item_id IS NULL
            GROUP BY oi.item_id, oi.order_no, co.customer_name
            ORDER BY oi.item_id
        '''
        
        cursor.execute(query, (order_no,))
        results = cursor.fetchall()
        print(f"🔍 DEBUG: Found {len(results)} items")
        
        # Order production wala function yahan bhi use kar rahe hain
        def extract_pieces_from_qty(qty, packing=48):
            """Extract required pieces from quantity string with actual packing value"""
            if not qty:
                return 0
            
            qty_str = str(qty).lower().strip()
            
            # If already in pieces format
            pieces_match = re.search(r'(\d+)\s*pcs', qty_str)
            if pieces_match:
                return int(pieces_match.group(1))
            
            # If in cartons/boxes format
            carton_match = re.search(r'(\d+)\s*(ctn|carton|cartons|box|boxes)', qty_str)
            if carton_match:
                cartons = int(carton_match.group(1))
                return cartons * packing  # Use actual packing from item data
            
            # If just a number (assume cartons)
            number_match = re.search(r'^(\d+)$', qty_str)
            if number_match:
                cartons = int(number_match.group(1))
                return cartons * packing  # Use actual packing from item data
            
            return 0
        
        items = []
        for row in results:
            # Get actual packing value from item data (index updated)
            item_packing = int(row[8]) if row[8] else 48
            
            # Calculate total pieces using proper function (index updated)
            pieces = extract_pieces_from_qty(row[3], item_packing)
            
            # Create proper quantity display (index updated)
            qty_str = str(row[3]).strip().lower() if row[3] else ''
            qty_display = f"{pieces} Pcs"  # Default value
            
            if 'ctn' in qty_str or 'carton' in qty_str:
                cartons = pieces // item_packing if item_packing > 0 else 0
                qty_display = f"{cartons} Ctn x {item_packing} Pcs = {pieces} Pcs"
            elif 'pcs' in qty_str:
                qty_display = f"{pieces} Pcs"
            else:
                if item_packing > 0 and pieces % item_packing == 0:
                    cartons = pieces // item_packing
                    qty_display = f"{cartons} Ctn x {item_packing} Pcs = {pieces} Pcs"
                else:
                    qty_display = f"{pieces} Pcs"
            
            qty_format = qty_display
            
            # Get production data (indices updated for customer_name)
            customer_name = row[13] if row[13] else 'Unknown Customer'
            produced_pieces = row[14] if row[14] else 0
            total_shafts = row[15] if row[15] else 0
            
            remaining_pieces = max(0, pieces - produced_pieces)
            
            # Create proper production status text with user format: "X Ctn x Packing = Total Pcs - Production = Balance Pcs"
            cartons = pieces // item_packing if item_packing > 0 and pieces % item_packing == 0 else 0
            if cartons > 0:
                production_status = f"{cartons} Ctn x {item_packing} Pcs = {pieces} Pcs - {produced_pieces} Pcs = Balance {remaining_pieces} Pcs"
            else:
                production_status = f"{pieces} Pcs - {produced_pieces} Pcs = Balance {remaining_pieces} Pcs"
            
            items.append({
                'id': row[0],
                'order_no': row[1],  # Order number added
                'size': row[2],      # Index updated
                'qty': qty_str,      # Original qty string  
                'qty_format': qty_format,  # Formatted display
                'production_status_text': production_status,
                'micron': row[4],    # Index updated
                'brand': row[5],     # Index updated
                'colour': row[6],    # Index updated
                'variety': row[7],   # Index updated
                'packing': row[8],   # Index updated
                'printed_matter': row[9],   # Index updated
                'unit_price': row[10],      # Index updated
                'amount': row[11],          # Index updated
                'notes': row[12],           # Index updated
                'party_name': customer_name,  # Customer name for frontend display
                'total_pieces': pieces,       # Total pieces for frontend display
                'required_pieces': pieces,
                'produced_pieces': produced_pieces,
                'remaining_pieces': remaining_pieces,
                'cartons': cartons,
                'production_status': 'completed' if remaining_pieces == 0 else ('in_progress' if produced_pieces > 0 else 'pending')
            })
        
        conn.close()
        print(f"🔍 DEBUG: Returning {len(items)} items")
        
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        print(f"❌ ERROR in get_order_items: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@bp.route('/api/production/matching-jambos', methods=['POST'])
def get_matching_jambos():
    """Get jambos matching item specifications"""
    try:
        data = request.get_json()
        colour = data.get('colour', '').strip()  # Remove leading/trailing spaces
        item_size = data.get('size', '')
        item_micron = data.get('micron', 37)
        search_text = data.get('search_text', '').strip()
        
        print(f"🔍 DEBUG: Matching criteria - colour: {colour}, size: {item_size}, micron: {item_micron}, search: {search_text}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query conditions
        where_conditions = []
        params = []
        
        # If direct jambo search is provided
        if search_text:
            where_conditions.append("(CAST(j.jambo_no AS TEXT) LIKE ? OR LOWER(j.party_name) LIKE LOWER(?) OR LOWER(j.colour) LIKE LOWER(?))")
            search_pattern = f'%{search_text}%'
            params.extend([search_pattern, search_pattern, search_pattern])
        else:
            # Use item specifications for matching
            if colour:
                # Exact match with trimmed values and case-insensitive
                where_conditions.append("LOWER(TRIM(j.colour)) = LOWER(TRIM(?))")
                params.append(colour)
            
            if item_micron:
                where_conditions.append("j.micron = ?")
                params.append(item_micron)
        
        # Always exclude closed jambos
        where_conditions.append("c.jambo_id IS NULL")
        
        # Construct final query with production data
        base_query = '''
            SELECT j.jambo_no, j.size_mm, j.size_meter, j.party_name, j.colour, j.micron, 
                   j.roll_no, j.net_weight, j.rate_kg, j.calculated_yard, j.date, 
                   j.balance_yard,
                   COALESCE(SUM(po.yards_used), 0) as used_yards,
                   CASE WHEN c.jambo_id IS NOT NULL THEN 'CLOSED' ELSE 'ACTIVE' END as status
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            LEFT JOIN production_orders po ON j.jambo_no = po.jambo_no
        '''
        
        if where_conditions:
            query = f"{base_query} WHERE {' AND '.join(where_conditions)} GROUP BY j.jambo_no, j.size_mm, j.size_meter, j.party_name, j.colour, j.micron, j.roll_no, j.net_weight, j.rate_kg, j.calculated_yard, j.date, j.balance_yard HAVING j.balance_yard > 0 ORDER BY j.balance_yard DESC, j.jambo_no ASC"
        else:
            query = f"{base_query} WHERE c.jambo_id IS NULL GROUP BY j.jambo_no, j.size_mm, j.size_meter, j.party_name, j.colour, j.micron, j.roll_no, j.net_weight, j.rate_kg, j.calculated_yard, j.date, j.balance_yard HAVING j.balance_yard > 0 ORDER BY j.balance_yard DESC, j.jambo_no ASC"
        
        print(f"🔍 DEBUG: SQL Query: {query}")
        print(f"🔍 DEBUG: SQL Params: {params}")
        
        cursor.execute(query, params)
        
        jambos = []
        for row in cursor.fetchall():
            jambo_no = row[0]
            balance_yard = row[11] if row[11] else 0  # balance_yard from database
            used_yards = row[12] if row[12] else 0  # used_yards from production_orders
            
            print(f"🔍 DEBUG: Processing Jambo #{jambo_no}:")
            print(f"- Colour: {row[4]}")
            print(f"- Balance: {balance_yard}")
            print(f"- Used: {used_yards}")
            
            if balance_yard > 0:  # Only include jambos with positive balance
                jambos.append({
                    'jambo_no': jambo_no,
                    'size_mm': row[1],
                    'size_meter': row[2],
                    'party_name': row[3],
                    'colour': row[4],
                    'micron': row[5],
                    'roll_no': row[6],
                    'weight_kg': row[7],
                    'rate': row[8],
                    'calculated_yard': row[9] if row[9] else 0,
                    'date': row[10],
                    'balance_yard': balance_yard,
                    'used_yards': used_yards,
                    'status': row[13]
                })
        
        print(f"🔍 DEBUG: Found {len(jambos)} matching jambos")
        
        conn.close()
        return jsonify({
            'success': True,
            'jambos': jambos
        })
        
    except Exception as e:
        print(f"❌ ERROR in get_matching_jambos: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@bp.route('/api/production/list')
def list_productions():
    """Get all production orders"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get production orders with complete details
        cursor.execute('''
            SELECT p.id, p.order_no, p.production_date, 
                   p.jambo_no, p.shafts_used, p.yards_used,
                   p.status, p.production_date as created_date,
                   co.customer_name,
                   oi.size as product_size, oi.qty,
                   p.produced_pieces
            FROM production_orders p
            LEFT JOIN customer_orders co ON p.order_no = co.order_no
            LEFT JOIN order_items oi ON p.item_id = oi.item_id AND p.order_no = oi.order_no
            ORDER BY p.production_date DESC
        ''')
        
        productions = []
        for row in cursor.fetchall():
            productions.append({
                'id': row[0],
                'order_no': row[1],
                'production_date': row[2],
                'jambo_no': row[3],
                'shafts': row[4],
                'yards': row[5],
                'status': row[6],
                'created_date': row[7],
                'customer': row[8] or 'N/A',
                'product': row[9] or 'N/A',
                'qty': row[10],
                'pieces': row[11],
                'date': row[2]  # Use production_date as date
            })
        
        conn.close()
        return jsonify({'success': True, 'productions': productions})
        
    except Exception as e:
        print(f"❌ ERROR in list_productions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/items/matching/<int:jambo_no>')
def get_matching_items(jambo_no):
    """Get matching order items for a jambo"""
    try:
        print(f"🔍 DEBUG: Finding matching items for jambo #{jambo_no}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get jambo details first
        cursor.execute("""
            SELECT size_mm, colour, micron
            FROM jambo_rolls
            WHERE jambo_no = ?
        """, (jambo_no,))
        
        jambo = cursor.fetchone()
        if not jambo:
            return jsonify({'success': False, 'message': 'Jambo not found'})
            
        jambo_size, jambo_colour, jambo_micron = jambo
        print(f"🔍 DEBUG: Jambo specs - size: {jambo_size}, colour: {jambo_colour}, micron: {jambo_micron}")
        
        # Get matching items from active orders with size check - Fixed to get produced pieces properly
        cursor.execute("""
            SELECT 
                oi.item_id,
                oi.order_no,
                oi.size,
                oi.colour,
                oi.micron,
                oi.qty,
                oi.packing,
                oi.brand,
                co.customer_name as party_name,
                COALESCE(SUM(po.produced_pieces), 0) as produced_pieces_total
            FROM order_items oi
            INNER JOIN customer_orders co ON oi.order_no = co.order_no
            LEFT JOIN production_orders po ON oi.order_no = po.order_no AND oi.item_id = po.item_id
            WHERE co.status IN ('Pending', 'In Progress')
            AND LOWER(TRIM(oi.colour)) = LOWER(TRIM(?))
            AND oi.micron = ?
            GROUP BY oi.item_id, oi.order_no, oi.size, oi.colour, oi.micron, oi.qty, oi.packing, oi.brand, co.customer_name
            ORDER BY co.order_date ASC
        """, (jambo_colour, jambo_micron))
        
        items = cursor.fetchall()
        print(f"🔍 DEBUG: Found {len(items)} matching items")
        
        # Convert to list of dicts and filter by item_width in Python
        import re
        items_list = []
        for item in items:
            # Extract width from size string (e.g., '1280mm x 4000m')
            size_str = item[2] or ''
            width_match = re.search(r'(\d+)', size_str)
            item_width = int(width_match.group(1)) if width_match else 0
            if item_width > jambo_size:
                continue  # Skip items that don't fit
            
            # Format quantity display and calculate total pieces - Order wala function use kar rahe hain
            def extract_pieces_from_qty(qty, packing=48):
                """Extract required pieces from quantity string with actual packing value"""
                if not qty:
                    return 0
                
                qty_str = str(qty).lower().strip()
                
                # If already in pieces format
                pieces_match = re.search(r'(\d+)\s*pcs', qty_str)
                if pieces_match:
                    return int(pieces_match.group(1))
                
                # If in cartons/boxes format
                carton_match = re.search(r'(\d+)\s*(ctn|carton|cartons|box|boxes)', qty_str)
                if carton_match:
                    cartons = int(carton_match.group(1))
                    return cartons * packing  # Use actual packing from item data
                
                # If just a number (assume cartons)
                number_match = re.search(r'^(\d+)$', qty_str)
                if number_match:
                    cartons = int(number_match.group(1))
                    return cartons * packing  # Use actual packing from item data
                
                return 0
            
            # Get actual packing value from item data
            item_packing = int(item[6]) if item[6] else 48
            
            # Calculate total pieces using proper function
            total_pieces = extract_pieces_from_qty(item[5], item_packing)
            
            # Calculate remaining pieces properly using total pieces and production data
            produced_pieces_from_db = item[9] if item[9] else 0  # produced_pieces_total from SQL query (index updated)
            remaining_pieces = max(0, total_pieces - produced_pieces_from_db)
            
            print(f"🔍 DEBUG: Item {item[0]} - Original qty: {item[5]}, Packing: {item_packing}, Total pieces: {total_pieces}, Produced: {produced_pieces_from_db}, Remaining: {remaining_pieces}")
            
            # Skip items that have no remaining pieces
            if remaining_pieces <= 0:
                print(f"🔍 DEBUG: Skipping item {item[0]} - no remaining pieces")
                continue
            
            # Create proper quantity display
            qty_str = str(item[5]).strip().lower() if item[5] else ''
            if 'ctn' in qty_str or 'carton' in qty_str:
                cartons = total_pieces // item_packing if item_packing > 0 else 0
                qty_display = f"{cartons} Ctn x {item_packing} Pcs = {total_pieces} Pcs"
            elif 'pcs' in qty_str:
                    qty_display = f"{total_pieces} Pcs"
            else:
                if item_packing > 0 and total_pieces % item_packing == 0:
                    cartons = total_pieces // item_packing
                    qty_display = f"{cartons} Ctn x {item_packing} Pcs = {total_pieces} Pcs"
                else:
                    qty_display = f"{total_pieces} Pcs"
            
            items_list.append({
                'id': item[0],
                'order_no': item[1],
                'size': item[2],
                'colour': item[3],
                'micron': item[4],
                'qty': qty_display,  # Use formatted display
                'packing': item[6],
                'brand': item[7],  # Brand field added
                'party_name': item[8],  # Index updated
                'remaining_pieces': remaining_pieces,  # Use properly calculated remaining pieces
                'produced_pieces': produced_pieces_from_db,  # Add produced pieces for frontend balance display
                'item_width': item_width,  # Add item width for frontend
                'total_pieces': total_pieces
            })
        
        conn.close()
        print(f"🔍 DEBUG: Returning {len(items_list)} items")
        
        return jsonify({
            'success': True,
            'items': items_list
        })
        
    except Exception as e:
        print(f"❌ ERROR getting matching items: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error getting matching items: {str(e)}'
        })

@bp.route('/api/jambos/active')
def get_active_jambos():
    """Get list of active jambos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active jambos (not closed and with balance)
        cursor.execute("""
            SELECT j.* 
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
            AND j.balance_yard > 0
            ORDER BY j.date DESC
        """)
        
        jambos = cursor.fetchall()
        
        # Convert to list of dicts
        jambos_list = []
        for jambo in jambos:
            jambos_list.append({
                'jambo_no': jambo[1],
                'date': jambo[2],
                'size_mm': jambo[3],
                'size_meter': jambo[4],
                'colour': jambo[5],
                'micron': jambo[6],
                'party_name': jambo[9],
                'balance_yard': jambo[14]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'jambos': jambos_list
        })
        
    except Exception as e:
        print(f"Error getting active jambos: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error getting active jambos: {str(e)}'
        })

@bp.route('/api/production/delete/<int:production_id>', methods=['DELETE'])
def delete_production(production_id):
    """Delete a production order and restore jambo balance"""
    try:
        print(f"🔍 DEBUG: Deleting production #{production_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # First get production details
            cursor.execute("""
                SELECT po.jambo_no, po.yards_used, j.calculated_yard,
                       COALESCE(SUM(po2.yards_used), 0) as total_used_yards
                FROM production_orders po
                LEFT JOIN jambo_rolls j ON po.jambo_no = j.jambo_no
                LEFT JOIN production_orders po2 ON j.jambo_no = po2.jambo_no AND po2.id != po.id
                WHERE po.id = ?
                GROUP BY po.jambo_no, po.yards_used, j.calculated_yard
            """, (production_id,))
            production = cursor.fetchone()
            if not production:
                print(f"❌ Production #{production_id} not found in DB!")
                return jsonify({
                    'success': False,
                    'message': f'Production #{production_id} not found'
                })
            jambo_no, yards_used, calculated_yard, other_used_yards = production
            new_balance = calculated_yard - other_used_yards  # Calculate new balance excluding this production
            print(f"🔍 DEBUG: Production details for #{production_id}:")
            print(f"- Jambo: #{jambo_no}")
            print(f"- Yards Used: {yards_used}")
            print(f"- Calculated Yard: {calculated_yard}")
            print(f"- Other Used Yards: {other_used_yards}")
            print(f"- New Balance: {new_balance}")
            # Update jambo balance
            cursor.execute("""
                UPDATE jambo_rolls
                SET balance_yard = ?
                WHERE jambo_no = ?
            """, (new_balance, jambo_no))
            print(f"🔄 Jambo balance updated!")
            # Stock transactions se bhi production entry delete karo
            cursor.execute("DELETE FROM stock_transactions WHERE reference_id = ? AND transaction_type = 'production'", (str(production_id),))
            print(f"🗑️ Stock transactions deleted!")
            # Delete production order
            cursor.execute("DELETE FROM production_orders WHERE id = ?", (production_id,))
            print(f"🗑️ Production order deleted!")
            conn.commit()
            print(f"✅ All changes committed!")
            conn.close()
            return jsonify({
                'success': True,
                'message': f'Production #{production_id} deleted successfully',
                'details': {
                    'jambo_no': jambo_no,
                    'yards_restored': yards_used,
                    'new_balance': new_balance
                }
            })
        except Exception as e:
            print(f"❌ ERROR deleting production: {str(e)}")
            conn.rollback()
            if 'conn' in locals():
                conn.close()
            return jsonify({
                'success': False,
                'message': f'Error deleting production: {str(e)}'
            })
    except Exception as e:
        print(f"❌ OUTER ERROR deleting production: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error deleting production: {str(e)}'
        })

@bp.route('/api/production/details/<int:production_id>')
def get_production_details(production_id):
    """Get details of a specific production entry"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get production details with related data
        cursor.execute('''
            SELECT 
                po.*,
                co.customer_name,
                oi.size as product_size, oi.colour, oi.micron, oi.brand, oi.qty,
                j.jambo_no as jambo_number, j.party_name, j.size_mm, j.size_meter as size_m, 
                j.net_weight as weight_kg, j.balance_yard
            FROM production_orders po
            LEFT JOIN customer_orders co ON po.order_no = co.order_no
            LEFT JOIN order_items oi ON po.order_no = oi.order_no AND po.item_id = oi.item_id
            LEFT JOIN jambo_rolls j ON po.jambo_no = j.jambo_no
            WHERE po.id = ?
        ''', (production_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                'success': False,
                'error': 'Production entry not found'
            }), 404
            
        # Convert to dictionary with proper field names
        production_data = {
            'id': row[0],
            'order_no': row[1],
            'item_id': row[2],
            'jambo_no': row[3],
            'produced_pieces': row[4],
            'production_date': row[5],
            'shafts_used': row[6],
            'yards_used': row[7],
            'status': row[8],
            'customer_name': row[9],
            'product_size': row[10],
            'colour': row[11],
            'micron': row[12],
            'brand': row[13],
            'qty': row[14],
            'jambo_number': row[15],
            'party_name': row[16],
            'jambo_size_mm': row[17],
            'jambo_size_m': row[18],
            'jambo_weight_kg': row[19],
            'jambo_balance_yard': row[20]
        }
        
        # Calculate pieces per shaft
        if production_data['shafts_used'] and production_data['shafts_used'] > 0:
            pieces_per_shaft = production_data['produced_pieces'] / production_data['shafts_used']
            production_data['pieces_per_shaft'] = round(pieces_per_shaft)
        else:
            production_data['pieces_per_shaft'] = 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'production': production_data
        })
        
    except Exception as e:
        print(f"Error getting production details: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/production/update/<int:production_id>', methods=['POST'])
def update_production(production_id):
    """Update production entry"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current production details
        cursor.execute('''
            SELECT po.*, j.balance_yard, j.jambo_no
            FROM production_orders po
            LEFT JOIN jambo_rolls j ON po.jambo_no = j.jambo_no
            WHERE po.id = ?
        ''', (production_id,))
        current_prod = cursor.fetchone()
        
        if not current_prod:
            return jsonify({
                'success': False,
                'error': 'Production entry not found'
            }), 404
        
        # Calculate yard difference
        old_yards = float(current_prod[7]) # yards_used from production_orders
        try:
            new_yards = float(data.get('yards_used', old_yards) or old_yards)
        except Exception as e:
            print("Yards conversion error:", e, data.get('yards_used'))
            new_yards = old_yards
        yards_difference = new_yards - old_yards
        print(f"DEBUG: old_yards={old_yards}, new_yards={new_yards}, diff={yards_difference}")
        
        # Update jambo balance
        if yards_difference != 0:
            new_balance = current_prod[9] - yards_difference # balance_yard from jambo_rolls
            cursor.execute('''
                UPDATE jambo_rolls 
                SET balance_yard = ? 
                WHERE jambo_no = ?
            ''', (max(0, new_balance), current_prod[10]))
        
        # Update production order
        cursor.execute('''
            UPDATE production_orders 
            SET shafts_used = ?,
                yards_used = ?,
                produced_pieces = ?,
                status = ?
            WHERE id = ?
        ''', (
            data.get('shafts_used', current_prod[6]),
            new_yards,
            data.get('produced_pieces', current_prod[4]),
            data.get('status', current_prod[8]),
            production_id
        ))
        # Debug: Check updated value
        cursor.execute('SELECT yards_used FROM production_orders WHERE id = ?', (production_id,))
        updated_yards = cursor.fetchone()
        print(f'AFTER UPDATE: yards_used in DB = {updated_yards}')
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Production updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating production: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 

@bp.route('/api/production/save', methods=['POST'])
def save_production():
    """Save production entry"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            cursor.execute('BEGIN TRANSACTION')
            
            # Get order item details with packing
            cursor.execute("""
                SELECT oi.size, oi.colour, oi.brand, oi.micron, oi.packing
                FROM order_items oi
                WHERE oi.item_id = ?
            """, (data['item_id'],))
            
            item = cursor.fetchone()
            if not item:
                raise ValueError("Order item not found")
                
            # Parse size (e.g. "63mm x 72 Yard" -> 63, 72)
            size_parts = item[0].lower().replace('yard', '').strip().split('x')
            size_mm = int(size_parts[0].strip().replace('mm', ''))
            size_yard = int(size_parts[1].strip())
            
            # Get packing value from order item, default to 72 if not available
            item_packing = int(item[4]) if item[4] else 72
            
            # Create or get stock item with packing value
            item_id = create_or_get_stock_item(
                cursor,
                size_mm=size_mm,
                size_yard=size_yard,
                color=item[1],
                brand=item[2],
                micron=item[3],
                packing=item_packing  # Pass actual packing value from order
            )
            
            # Add production entry
            cursor.execute("""
                INSERT INTO production_orders (
                    order_no, item_id, jambo_no, produced_pieces,
                    production_date, shafts_used, yards_used, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['order_no'], data['item_id'], data['jambo_no'],
                data['pieces'], data['date'], data['shafts'],
                data['yards'], 'Completed'
            ))
            
            production_id = cursor.lastrowid
            
            # Roman Urdu: Har production ke sath stock_transactions table mai IN entry insert kar rahe hain
            add_stock_transaction(
                cursor,
                item_id=item_id,
                transaction_type='production',
                quantity=data['pieces'],
                reference_id=str(production_id),
                transaction_date=data['date']
            )
            
            # Update jambo balance
            cursor.execute("""
                UPDATE jambo_rolls 
                SET balance_yard = balance_yard - ?
                WHERE jambo_no = ?
            """, (data['yards'], data['jambo_no']))
            
            # Commit transaction
            cursor.execute('COMMIT')
            
            return jsonify({
                'success': True,
                'message': 'Production saved successfully'
            })
            
        except Exception as e:
            cursor.execute('ROLLBACK')
            raise e
            
    except Exception as e:
        print(f"Error saving production: {e}")
        return jsonify({
            'success': False,
            'message': f'Error saving production: {e}'
        })
        
    finally:
        if conn:
            conn.close() 

@bp.route('/production/data')
def production_data():
    """Production data table page"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Roman Urdu: Production orders ko join kar ke sari info lao, shaft_pcs ko calculate karo
        cursor.execute('''
            SELECT po.id, po.order_no, co.customer_name, oi.size, po.jambo_no, po.shafts_used, 
                   po.produced_pieces, po.yards_used, po.status, po.production_date
            FROM production_orders po
            LEFT JOIN customer_orders co ON po.order_no = co.order_no
            LEFT JOIN order_items oi ON po.item_id = oi.item_id
            LEFT JOIN jambo_rolls jr ON po.jambo_no = jr.jambo_no
            ORDER BY po.production_date DESC
        ''')
        rows = cursor.fetchall()
        productions = []
        for row in rows:
            shafts = row[5] or 0
            produced_pieces = row[6] or 0
            shaft_pcs = produced_pieces // shafts if shafts > 0 else 0
            actions = f'''
                <a href="/production/edit/{row[0]}" class="btn btn-sm btn-warning me-1"><i class="fas fa-edit"></i></a>
                <button class="btn btn-sm btn-danger" onclick="deleteProductionItem({row[0]})"><i class="fas fa-trash"></i></button>
            '''
            productions.append({
                'production_id': row[0],
                'order_no': row[1],
                'customer': row[2] or '',
                'product': row[3] or '',
                'jambo': row[4] or '',
                'total_shafts': shafts,
                'shaft_pcs': shaft_pcs,
                'total_pcs': produced_pieces,
                'yards': row[7] or '',
                'status': row[8] or '',
                'date': row[9] or '',
                'actions': actions
            })
        conn.close()
        return render_template('production_data.html', productions=productions)
    except Exception as e:
        print(f"Error loading production data: {e}")
        return render_template('production_data.html', productions=[]) 