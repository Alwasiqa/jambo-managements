"""
Reports routes
"""
from flask import Blueprint, render_template, jsonify, request, send_file, redirect, url_for, flash
from database import get_db_connection, get_next_bill_number
from datetime import datetime
import json
import io
import xlsxwriter
from collections import defaultdict

bp = Blueprint('reports', __name__)

@bp.route('/')
def reports_dashboard():
    """Reports dashboard"""
    return render_template('reports.html')

@bp.route('/jambo-ledger')
def jambo_ledger():
    """Jambo ledger report"""
    return render_template('jambo_ledger.html')

@bp.route('/stock')
def stock_report():
    """Stock report"""
    return render_template('stock_report.html')

@bp.route('/stock/filters')
def get_stock_filters():
    """Get stock filters"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get unique values for filters
        cursor.execute("SELECT DISTINCT size_mm FROM stock_items ORDER BY size_mm")
        sizes = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT color FROM stock_items ORDER BY color")
        colors = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT brand FROM stock_items ORDER BY brand")
        brands = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT micron FROM stock_items ORDER BY micron")
        microns = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'sizes': sizes,
            'colors': colors,
            'brands': brands,
            'microns': microns
        })
        
    except Exception as e:
        print(f"Error getting stock filters: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting stock filters: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/stock/items')
def get_stock_items():
    """Get stock items (production production_orders se, sales stock_transactions se, mapping fix)"""
    try:
        filters = json.loads(request.args.get('filters', '{}'))
        conn = get_db_connection()
        cursor = conn.cursor()

        # Roman Urdu: Production production_orders se, sales stock_transactions se (mapping fix)
        query = '''
            SELECT 
                oi.size, oi.colour, oi.brand, oi.micron,
                SUM(po.produced_pieces) as production,
                (
                    SELECT COALESCE(SUM(st.quantity), 0)
                    FROM stock_transactions st
                    JOIN stock_items si ON st.item_id = si.id
                    WHERE st.transaction_type = 'sale'
                    AND si.size_mm = CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER)
                    AND si.size_yard = CAST(SUBSTR(oi.size, INSTR(oi.size, 'x')+1, INSTR(oi.size, 'Yard')-INSTR(oi.size, 'x')-1) AS INTEGER)
                    AND si.color = oi.colour
                    AND si.brand = oi.brand
                    AND si.micron = oi.micron
                ) as sales
            FROM production_orders po
            JOIN order_items oi ON po.item_id = oi.item_id
            WHERE 1=1
        '''
        params = []
        if filters.get('size_mm'):
            query += ' AND CAST(SUBSTR(oi.size, 1, INSTR(oi.size, "mm")-1) AS INTEGER) = ?'
            params.append(filters['size_mm'])
        if filters.get('color'):
            query += ' AND oi.colour = ?'
            params.append(filters['color'])
        if filters.get('brand'):
            query += ' AND oi.brand = ?'
            params.append(filters['brand'])
        if filters.get('micron'):
            query += ' AND oi.micron = ?'
            params.append(filters['micron'])
        query += ' GROUP BY oi.size, oi.colour, oi.brand, oi.micron'

        cursor.execute(query, params)
        items = []
        for row in cursor.fetchall():
            production = row[4] or 0
            sales = row[5] or 0
            balance = production - sales
            # Sirf woh items add karo jinka balance 0 se zyada hai
            if balance > 0:
                items.append({
                    'size_mm': row[0].split('x')[0].replace('mm','').strip(),
                    'size_yard': row[0].split('x')[1].replace('Yard','').strip() if 'x' in row[0] else '',
                    'color': row[1],
                    'brand': row[2],
                    'micron': row[3],
                    'production': production,
                    'sales': sales,
                    'balance': balance
                })
        return jsonify({
            'success': True,
            'items': items
        })
    except Exception as e:
        print(f"Error getting stock items: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting stock items: {e}'
        })
    finally:
        if conn:
            conn.close()

@bp.route('/api/stock/items/<int:item_id>')
def get_stock_item_details(item_id):
    """Get stock item details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get item details
        cursor.execute("""
            SELECT size_mm, size_yard, color, brand, micron
            FROM stock_items
            WHERE id = ?
        """, (item_id,))
        
        item = cursor.fetchone()
        if not item:
            return jsonify({
                'success': False,
                'message': 'Item not found'
            })
            
        # Get transactions
        cursor.execute("""
            SELECT transaction_date, transaction_type, quantity, reference_id
            FROM stock_transactions
            WHERE item_id = ?
            ORDER BY transaction_date
        """, (item_id,))
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                'transaction_date': row[0],
                'transaction_type': row[1],
                'quantity': row[2],
                'reference_id': row[3]
            })
            
        return jsonify({
            'success': True,
            'item': {
                'size_mm': item[0],
                'size_yard': item[1],
                'color': item[2],
                'brand': item[3],
                'micron': item[4]
            },
            'transactions': transactions
        })
        
    except Exception as e:
        print(f"Error getting stock item details: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting stock item details: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/stock/export')
def export_stock():
    """Export stock report to Excel"""
    try:
        filters = json.loads(request.args.get('filters', '{}'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get stock items with same filters as get_stock_items
        query = """
            SELECT i.size_mm, i.size_yard, i.color, i.brand, i.micron,
                   COALESCE(SUM(CASE WHEN t.transaction_type = 'production' THEN t.quantity ELSE 0 END), 0) as production,
                   COALESCE(SUM(CASE WHEN t.transaction_type = 'sale' THEN t.quantity ELSE 0 END), 0) as sales
            FROM stock_items i
            LEFT JOIN stock_transactions t ON i.id = t.item_id
            WHERE 1=1
        """
        params = []
        
        if filters.get('size_mm'):
            query += " AND i.size_mm = ?"
            params.append(filters['size_mm'])
            
        if filters.get('color'):
            query += " AND i.color = ?"
            params.append(filters['color'])
            
        if filters.get('brand'):
            query += " AND i.brand = ?"
            params.append(filters['brand'])
            
        if filters.get('micron'):
            query += " AND i.micron = ?"
            params.append(filters['micron'])
            
        query += " GROUP BY i.size_mm, i.size_yard, i.color, i.brand, i.micron"
        
        cursor.execute(query, params)
        items = cursor.fetchall()
        
        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Add headers
        headers = ['Item Description', 'Production', 'Sales', 'Balance']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Add data
        for row, item in enumerate(items, start=1):
            description = f"{item[0]}mm x {item[1]} Yard {item[2]} {item[3]} {item[4]}mic"
            production = item[5]
            sales = item[6]
            balance = production - sales
            
            worksheet.write(row, 0, description)
            worksheet.write(row, 1, production)
            worksheet.write(row, 2, sales)
            worksheet.write(row, 3, balance)
        
        workbook.close()
        
        # Send file
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'stock_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
        
    except Exception as e:
        print(f"Error exporting stock: {e}")
        return jsonify({
            'success': False,
            'message': f'Error exporting stock: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/stock/items/<path:item_id>/ledger')
def get_stock_item_ledger(item_id):
    """Get stock item ledger with party names"""
    try:
        # Parse composite item ID
        size_mm, size_yard, color, brand, micron = item_id.split('-')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get packing info from stock_items first (for manually created items)
        cursor.execute("""
            SELECT packing
            FROM stock_items
            WHERE size_mm = ?
            AND size_yard = ?
            AND color = ?
            AND brand = ?
            AND micron = ?
            LIMIT 1
        """, (size_mm, size_yard, color, brand, micron))
        
        packing = cursor.fetchone()
        packing_size = 0
        
        if packing and packing[0]:
            packing_size = int(packing[0])
        else:
            # If not found in stock_items, try order_items
            cursor.execute("""
                SELECT DISTINCT oi.packing
                FROM order_items oi
                WHERE CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER) = ?
                AND CAST(SUBSTR(
                    oi.size, 
                    INSTR(oi.size, 'x') + 1,
                    INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
                ) AS INTEGER) = ?
                AND oi.colour = ?
                AND oi.brand = ?
                AND oi.micron = ?
                LIMIT 1
            """, (size_mm, size_yard, color, brand, micron))
            
            packing = cursor.fetchone()
            packing_size = int(packing[0]) if packing and packing[0] and str(packing[0]).isdigit() else 72
        
        # Get production transactions
        cursor.execute("""
            SELECT 
                po.production_date as transaction_date,
                po.id as reference_id,
                jr.party_name,
                'production' as transaction_type,
                po.produced_pieces as quantity
            FROM production_orders po
            JOIN order_items oi ON po.item_id = oi.item_id
            JOIN jambo_rolls jr ON po.jambo_no = jr.jambo_no
            WHERE CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER) = ?
            AND CAST(SUBSTR(
                oi.size, 
                INSTR(oi.size, 'x') + 1,
                INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
            ) AS INTEGER) = ?
            AND oi.colour = ?
            AND oi.brand = ?
            AND oi.micron = ?
            ORDER BY po.production_date
        """, (size_mm, size_yard, color, brand, micron))
        production_rows = cursor.fetchall()

        # Roman Urdu: Ab sale (OUT) transactions stock_transactions table se nikal rahe hain
        cursor.execute("""
            SELECT 
                st.transaction_date,
                st.reference_id,
                st.transaction_type,
                st.quantity
            FROM stock_items si
            JOIN stock_transactions st ON si.id = st.item_id
            WHERE si.size_mm = ?
            AND si.size_yard = ?
            AND si.color = ?
            AND si.brand = ?
            AND si.micron = ?
            AND st.transaction_type = 'sale'
            ORDER BY st.transaction_date
        """, (size_mm, size_yard, color, brand, micron))
        sale_rows = cursor.fetchall()

        # Roman Urdu: Har sale row ke liye party_name bills table se nikal rahe hain
        sale_rows_with_party = []
        for row in sale_rows:
            transaction_date, reference_id, transaction_type, quantity = row
            # Bill no se customer_name nikalain
            cursor.execute("SELECT customer_name FROM bills WHERE bill_no = ?", (reference_id,))
            bill = cursor.fetchone()
            party_name = bill[0] if bill else ''
            sale_rows_with_party.append((transaction_date, reference_id, party_name, transaction_type, quantity))

        # Roman Urdu: Production aur Sale transactions ko merge kar ke date ke hisaab se sort kar rahe hain
        all_rows = [
            {
                'transaction_date': row[0],
                'reference_id': str(row[1]),
                'party_name': row[2],
                'transaction_type': row[3],
                'quantity': row[4]
            } for row in production_rows
        ] + [
            {
                'transaction_date': row[0],
                'reference_id': str(row[1]),
                'party_name': row[2],
                'transaction_type': row[3],
                'quantity': row[4]
            } for row in sale_rows_with_party
        ]
        all_rows.sort(key=lambda x: x['transaction_date'])

        transactions = []
        running_balance = 0
        for row in all_rows:
            quantity = row['quantity']
            if row['transaction_type'] == 'production':
                running_balance += quantity
            else:
                running_balance -= quantity
            # Calculate cartons and loose pieces
            cartons = quantity // packing_size if packing_size > 0 else 0
            loose = quantity % packing_size if packing_size > 0 else quantity
            transactions.append({
                'transaction_date': row['transaction_date'],
                'reference_id': row['reference_id'],
                'party_name': row['party_name'],
                'transaction_type': row['transaction_type'],
                'quantity': quantity,
                'cartons': cartons,
                'loose': loose,
                'running_balance': running_balance,
                'running_balance_cartons': running_balance // packing_size if packing_size > 0 else 0,
                'running_balance_loose': running_balance % packing_size if packing_size > 0 else running_balance
            })
        return jsonify({
            'success': True,
            'transactions': transactions,
            'current_balance': running_balance,
            'packing_size': packing_size,
            'current_balance_cartons': running_balance // packing_size if packing_size > 0 else 0,
            'current_balance_loose': running_balance % packing_size if packing_size > 0 else running_balance
        })
        
    except Exception as e:
        print(f"Error getting stock item ledger: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting stock item ledger: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/jambo/<int:jambo_no>')
def get_jambo_details(jambo_no):
    """Get jambo details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT jambo_no, date, size_mm, size_meter, colour, micron, 
                   roll_no, net_weight, party_name, calculated_yard, 
                   actual_yard, rate_kg, amount, balance_yard
            FROM jambo_rolls
            WHERE jambo_no = ?
        """, (jambo_no,))
        
        jambo = cursor.fetchone()
        
        if not jambo:
            return jsonify({
                'success': False,
                'message': 'Jambo not found'
            })
            
        return jsonify({
            'success': True,
            'jambo': {
                'jambo_no': jambo[0],
                'date': jambo[1],
                'size_mm': jambo[2],
                'size_meter': jambo[3],
                'colour': jambo[4],
                'micron': jambo[5],
                'roll_no': jambo[6],
                'net_weight': jambo[7],
                'party_name': jambo[8],
                'calculated_yard': jambo[9],
                'actual_yard': jambo[10],
                'rate_kg': jambo[11],
                'amount': jambo[12],
                'balance_yard': jambo[13]
            }
        })
        
    except Exception as e:
        print(f"Error getting jambo details: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting jambo details: {e}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/jambo/<int:jambo_no>/ledger')
def get_jambo_ledger(jambo_no):
    """Get jambo ledger entries"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get opening (jambo) details
        cursor.execute("SELECT challan_no FROM jambo_rolls WHERE jambo_no = ?", (jambo_no,))
        opening_challan = cursor.fetchone()
        opening_challan_no = opening_challan[0] if opening_challan and opening_challan[0] else None

        # Get production entries
        cursor.execute("""
            SELECT p.production_date, co.customer_name, oi.size,
                   p.shafts_used, p.produced_pieces, p.yards_used,
                   p.status, p.id, jr.challan_no
            FROM production_orders p
            JOIN customer_orders co ON p.order_no = co.order_no
            JOIN order_items oi ON p.item_id = oi.item_id
            JOIN jambo_rolls jr ON p.jambo_no = jr.jambo_no
            WHERE p.jambo_no = ?
            ORDER BY p.production_date
        """, (jambo_no,))
        
        entries = []
        for row in cursor.fetchall():
            entries.append({
                'production_date': row[0],
                'customer_name': row[1],
                'size': row[2],
                'shafts_used': row[3],
                'produced_pieces': row[4],
                'yards_used': row[5],
                'status': row[6],
                'reference_id': row[7],  # Roman Urdu: Production ID as reference
                'challan_no': row[8]     # Roman Urdu: Challan No
            })
            
        # Get OUT (sale) transactions for this jambo
        cursor.execute("""
            SELECT st.transaction_date, b.customer_name, oi.size, NULL as shafts_used, NULL as produced_pieces, NULL as yards_used, 'Sale' as status, st.reference_id, NULL as challan_no
            FROM stock_transactions st
            JOIN stock_items si ON st.item_id = si.id
            JOIN order_items oi ON si.size_mm = CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER)
                AND si.size_yard = CAST(SUBSTR(oi.size, INSTR(oi.size, 'x')+1, INSTR(oi.size, 'Yard')-INSTR(oi.size, 'x')-1) AS INTEGER)
                AND si.color = oi.colour
                AND si.brand = oi.brand
                AND si.micron = oi.micron
            JOIN bills b ON st.reference_id = b.bill_no
            WHERE st.transaction_type = 'sale' AND si.id IN (
                SELECT id FROM stock_items WHERE id = si.id AND si.id IS NOT NULL
            ) AND st.transaction_date IS NOT NULL AND st.transaction_date != ''
            AND st.item_id IN (
                SELECT id FROM stock_items WHERE id = si.id AND si.id IS NOT NULL
            )
            AND st.transaction_date >= (SELECT date FROM jambo_rolls WHERE jambo_no = ?)
        """, (jambo_no,))
        sale_entries = cursor.fetchall()
        for row in sale_entries:
            entries.append({
                'production_date': row[0],
                'customer_name': row[1],
                'size': row[2],
                'shafts_used': row[3],
                'produced_pieces': row[4],
                'yards_used': row[5],
                'status': row[6],
                'reference_id': row[7],
                'challan_no': row[8]
            })
        # Sort all entries by production_date
        entries.sort(key=lambda x: x['production_date'])

        # Remove sale (OUT) entries, sirf production/original entries rakhain
        entries = [e for e in entries if e.get('status') != 'Sale']

        return jsonify({
            'success': True,
            'entries': entries,
            'opening_challan_no': opening_challan_no
        })
        
    except Exception as e:
        print(f"Error getting jambo ledger: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting jambo ledger: {e}'
        })
        
    finally:
        if conn:
            conn.close() 

@bp.route('/stock/search')
def search_stock_items():
    """Search stock items (production + manually created)"""
    try:
        query = request.args.get('query', '').strip().lower()
        if not query:
            return jsonify({
                'success': True,
                'items': []
            })
        
        # Clean query for better matching
        clean_query = query.replace(' ', '%')  # Replace spaces with % for partial matching
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Search in production orders and order items
        cursor.execute("""
            SELECT DISTINCT
                CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER) as size_mm,
                CAST(SUBSTR(
                    oi.size, 
                    INSTR(oi.size, 'x') + 1,
                    INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
                ) AS INTEGER) as size_yard,
                oi.colour as color,
                oi.brand,
                oi.micron,
                COALESCE(SUM(po.produced_pieces), 0) as production
            FROM production_orders po
            JOIN order_items oi ON po.item_id = oi.item_id
            WHERE LOWER(oi.size) LIKE ? 
            OR LOWER(oi.colour) LIKE ?
            OR LOWER(oi.brand) LIKE ?
            OR oi.micron LIKE ?
            OR CAST(SUBSTR(
                oi.size, 
                INSTR(oi.size, 'x') + 1,
                INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
            ) AS TEXT) LIKE ?
            OR LOWER(oi.size) LIKE ?
            GROUP BY 
                CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER),
                CAST(SUBSTR(
                    oi.size, 
                    INSTR(oi.size, 'x') + 1,
                    INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
                ) AS INTEGER),
                oi.colour,
                oi.brand,
                oi.micron
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{clean_query}%"))
        
        production_items = []
        for row in cursor.fetchall():
            production_items.append({
                'size_mm': row[0],
                'size_yard': row[1],
                'color': row[2],
                'brand': row[3],
                'micron': row[4],
                'production': row[5],
                'description': f"{row[0]}mm x {row[1]} Yard {row[2]} {row[3]} {row[4]}mic",
                'source': 'production'
            })
        
        # Search in manually created stock items
        cursor.execute("""
            SELECT 
                size_mm, size_yard, color, brand, micron, packing,
                COALESCE(SUM(CASE WHEN st.transaction_type = 'production' THEN st.quantity ELSE 0 END), 0) as production
            FROM stock_items si
            LEFT JOIN stock_transactions st ON si.id = st.item_id
            WHERE LOWER(CAST(si.size_mm AS TEXT)) LIKE ? 
            OR LOWER(CAST(si.size_yard AS TEXT)) LIKE ?
            OR LOWER(si.color) LIKE ?
            OR LOWER(si.brand) LIKE ?
            OR LOWER(CAST(si.micron AS TEXT)) LIKE ?
            OR LOWER(CONCAT(CAST(si.size_mm AS TEXT), 'mm x ', CAST(si.size_yard AS TEXT), ' Yard')) LIKE ?
            GROUP BY si.size_mm, si.size_yard, si.color, si.brand, si.micron, si.packing
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{clean_query}%"))
        
        manual_items = []
        for row in cursor.fetchall():
            manual_items.append({
                'size_mm': row[0],
                'size_yard': row[1],
                'color': row[2],
                'brand': row[3],
                'micron': row[4],
                'packing': row[5] or 72,
                'production': row[6],
                'description': f"{row[0]}mm x {row[1]} Yard {row[2]} {row[3]} {row[4]}mic",
                'source': 'manual'
            })
        
        # Combine and deduplicate items
        all_items = production_items + manual_items
        unique_items = {}
        
        for item in all_items:
            key = f"{item['size_mm']}-{item['size_yard']}-{item['color']}-{item['brand']}-{item['micron']}"
            if key not in unique_items:
                unique_items[key] = item
            else:
                # If item exists, combine production values
                unique_items[key]['production'] += item['production']
        
        # Convert back to list and limit results
        items = list(unique_items.values())[:10]
            
        return jsonify({
            'success': True,
            'items': items
        })
        
    except Exception as e:
        print(f"Error searching stock items: {e}")
        return jsonify({
            'success': False,
            'message': f'Error searching stock items: {e}'
        })
        
    finally:
        if conn:
            conn.close() 

@bp.route('/jambo/search')
def search_jambos():
    """Search jambos by number, color, or party name"""
    try:
        query = request.args.get('query', '').strip().lower()
        if not query:
            return jsonify({
                'success': True,
                'jambos': []
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Search in jambo_rolls table
        cursor.execute("""
            SELECT jambo_no, date, colour, party_name, size_mm, size_meter, micron, balance_yard
            FROM jambo_rolls
            WHERE LOWER(CAST(jambo_no AS TEXT)) LIKE ? 
            OR LOWER(colour) LIKE ?
            OR LOWER(party_name) LIKE ?
            ORDER BY jambo_no DESC
            LIMIT 10
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        
        jambos = []
        for row in cursor.fetchall():
            jambos.append({
                'jambo_no': row[0],
                'date': row[1],
                'colour': row[2],
                'party_name': row[3],
                'size_mm': row[4],
                'size_meter': row[5],
                'micron': row[6],
                'balance_yard': row[7],
                'description': f"#{row[0]} - {row[2]} ({row[3]}) - {row[4]}mm x {row[5]}m"
            })
            
        return jsonify({
            'success': True,
            'jambos': jambos
        })
        
    except Exception as e:
        print(f"Error searching jambos: {e}")
        return jsonify({
            'success': False,
            'message': f'Error searching jambos: {e}'
        })
        
    finally:
        if conn:
            conn.close() 

@bp.route('/api/customers')
def get_customers():
    """Get all customers for search"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT party_name, phone, address 
            FROM parties 
            WHERE is_active = 1
            ORDER BY party_name
        """)
        
        customers = [{
            'name': row[0],
            'phone': row[1] or '',
            'address': row[2] or ''
        } for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'customers': customers
        })
        
    except Exception as e:
        print(f"Error getting customers: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/customers/search')
def search_customers():
    """Search customers for autocomplete (parties + customer_orders union, partial match anywhere)"""
    try:
        search = request.args.get('term', '').strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        # Parties table se (partial match anywhere)
        cursor.execute("""
            SELECT DISTINCT name 
            FROM parties 
            WHERE party_type = 'customer'
            AND is_active = 1
            AND name IS NOT NULL 
            AND name != ''
            AND instr(LOWER(name), ?) > 0
            LIMIT 50
        """, (search,))
        party_customers = set(row[0] for row in cursor.fetchall())
        # customer_orders table se (partial match anywhere)
        cursor.execute("""
            SELECT DISTINCT customer_name 
            FROM customer_orders 
            WHERE customer_name IS NOT NULL 
            AND customer_name != ''
            AND instr(LOWER(customer_name), ?) > 0
            LIMIT 50
        """, (search,))
        order_customers = set(row[0] for row in cursor.fetchall())
        # Union
        all_customers = sorted(party_customers.union(order_customers))
        return jsonify(all_customers)
    except Exception as e:
        print(f"Customer search error: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close()

@bp.route('/api/suppliers/search')
def search_suppliers():
    """Roman Urdu: Suppliers ka search (bulk jambo ki tarah)"""
    try:
        search = request.args.get('term', '').strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        # Bulk jambo ki tarah suppliers nikal rahe hain
        cursor.execute("""
            SELECT DISTINCT name 
            FROM parties 
            WHERE party_type = 'supplier' 
            AND is_active = 1 
            AND name IS NOT NULL 
            AND name != ''
            AND LOWER(name) LIKE ?
            ORDER BY name
        """, (f'%{search}%',))
        results = [row[0] for row in cursor.fetchall()]
        return jsonify(results)
    except Exception as e:
        print(f"Supplier search error: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close()

@bp.route('/api/stock/search')
def search_stock():
    """Search stock items (production + manually created)"""
    try:
        search = request.args.get('term', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get packing info first
        cursor.execute("""
            SELECT DISTINCT size, packing
            FROM order_items
            WHERE packing IS NOT NULL AND packing != ''
            GROUP BY size, packing
        """)
        packing_info = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Search in production orders and order items
        cursor.execute("""
            SELECT 
                DISTINCT
                CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER) as size_mm,
                CAST(SUBSTR(
                    oi.size, 
                    INSTR(oi.size, 'x') + 1,
                    INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
                ) AS INTEGER) as size_yard,
                oi.colour as color,
                oi.brand,
                oi.micron,
                COALESCE(SUM(po.produced_pieces), 0) as production
            FROM production_orders po
            JOIN order_items oi ON po.item_id = oi.item_id
            WHERE LOWER(oi.size) LIKE LOWER(?) 
            OR LOWER(oi.colour) LIKE LOWER(?)
            OR LOWER(oi.brand) LIKE LOWER(?)
            OR oi.micron LIKE ?
            GROUP BY 
                CAST(SUBSTR(oi.size, 1, INSTR(oi.size, 'mm')-1) AS INTEGER),
                CAST(SUBSTR(
                    oi.size, 
                    INSTR(oi.size, 'x') + 1,
                    INSTR(oi.size, 'Yard') - INSTR(oi.size, 'x') - 1
                ) AS INTEGER),
                oi.colour,
                oi.brand,
                oi.micron
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
        
        production_items = []
        for row in cursor.fetchall():
            size = f"{row[0]}mm x {row[1]} Yard"
            description = f"{row[0]}mm x {row[1]} Yard {row[2]} {row[3]} {row[4]}mic"
            
            # Get packing from packing_info
            packing = packing_info.get(size, '72')  # Default to 72 if not found
            if packing:
                try:
                    packing = int(str(packing).strip())
                except:
                    packing = 72
            
            production_items.append({
                'size': size,
                'colour': row[2],
                'brand': row[3],
                'mic': row[4],
                'packing': packing,
                'production': row[5],
                'description': description,
                'source': 'production'
            })
        
        # Search in manually created stock items
        cursor.execute("""
            SELECT 
                size_mm, size_yard, color, brand, micron, packing,
                COALESCE(SUM(CASE WHEN st.transaction_type = 'production' THEN st.quantity ELSE 0 END), 0) as production
            FROM stock_items si
            LEFT JOIN stock_transactions st ON si.id = st.item_id
            WHERE LOWER(CAST(si.size_mm AS TEXT)) LIKE LOWER(?) 
            OR LOWER(si.color) LIKE LOWER(?)
            OR LOWER(si.brand) LIKE LOWER(?)
            OR LOWER(CAST(si.micron AS TEXT)) LIKE LOWER(?)
            GROUP BY si.size_mm, si.size_yard, si.color, si.brand, si.micron, si.packing
        """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
        
        manual_items = []
        for row in cursor.fetchall():
            size = f"{row[0]}mm x {row[1]} Yard"
            description = f"{row[0]}mm x {row[1]} Yard {row[2]} {row[3]} {row[4]}mic"
            
            # Use packing from database or default
            packing = row[5] or 72
            if packing:
                try:
                    packing = int(str(packing).strip())
                except:
                    packing = 72
            
            manual_items.append({
                'size': size,
                'colour': row[2],
                'brand': row[3],
                'mic': row[4],
                'packing': packing,
                'production': row[6],
                'description': description,
                'source': 'manual'
            })
        
        # Combine and deduplicate items
        all_items = production_items + manual_items
        unique_items = {}
        
        for item in all_items:
            key = f"{item['size']}-{item['colour']}-{item['brand']}-{item['mic']}"
            if key not in unique_items:
                unique_items[key] = item
            else:
                # If item exists, combine production values
                unique_items[key]['production'] += item['production']
        
        # Convert back to list, sort by relevance, and limit results
        items = list(unique_items.values())
        items.sort(key=lambda x: (
            # Sort by exact match first
            0 if search.lower() in x['size'].lower() else 1,
            # Then by production amount
            -x['production']
        ))
        items = items[:10]
        
        print(f"Found items: {items}")
        return jsonify(items)
        
    except Exception as e:
        print(f"Stock search error: {e}")
        return jsonify([])
        
    finally:
        if conn:
            conn.close()

@bp.route('/generate_bill', methods=['GET', 'POST'])
def generate_bill():
    """Generate bill directly without order"""
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get form data
            bill_data = {
                'customer_name': request.form.get('customer_name'),
                'date': request.form.get('date'),
                'bill_no': request.form.get('bill_no'),
                'items': []
            }
            
            # Save bill header
            # Roman Urdu: Agar bill_no already exist karta hai to naya bill_no generate karo
            cursor.execute("SELECT COUNT(*) FROM bills WHERE bill_no = ?", (bill_data['bill_no'],))
            if cursor.fetchone()[0] > 0:
                bill_data['bill_no'] = get_next_bill_number()
            cursor.execute("""
                INSERT INTO bills (bill_no, date, customer_name)
                VALUES (?, ?, ?)
            """, (bill_data['bill_no'], bill_data['date'], bill_data['customer_name']))
            
            # Get items data
            for i in range(10):
                if request.form.get(f'qty_{i}'):
                    item = {
                        'qty': request.form.get(f'qty_{i}'),
                        'size': request.form.get(f'size_{i}'),
                        'colour': request.form.get(f'colour_{i}'),
                        'brand': request.form.get(f'brand_{i}'),
                        'mic': request.form.get(f'mic_{i}'),
                        'printed': request.form.get(f'printed_{i}'),
                        'varity': request.form.get(f'varity_{i}'),
                        'per_ctn_qty': request.form.get(f'per_ctn_qty_{i}'),
                        'rate': request.form.get(f'rate_{i}')
                    }
                    # Roman Urdu: Yahan CTN+ROLL display string bana rahe hain
                    try:
                        qty = int(item['qty']) if item['qty'] else 0
                        per_ctn_qty = int(item['per_ctn_qty']) if item['per_ctn_qty'] else 0
                        cartons = qty // per_ctn_qty if per_ctn_qty > 0 else 0
                        loose = qty % per_ctn_qty if per_ctn_qty > 0 else qty
                        if per_ctn_qty > 0:
                            if loose == 0:
                                qty_display = f"{cartons} CTN"
                            else:
                                qty_display = f"{cartons} CTN + {loose} ROLL" if cartons > 0 else f"{loose} ROLL"
                        else:
                            qty_display = f"{qty} ROLL"
                    except Exception:
                        qty_display = "-"
                    item['qty_display'] = qty_display
                    bill_data['items'].append(item)
                    
                    # Save bill item
                    cursor.execute("""
                        INSERT INTO bill_items (
                            bill_no, qty, size, colour, brand, mic, 
                            printed, varity, per_ctn_qty, rate
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bill_data['bill_no'], item['qty'], item['size'],
                        item['colour'], item['brand'], item['mic'],
                        item['printed'], item['varity'], item['per_ctn_qty'],
                        item['rate']
                    ))
                    # Roman Urdu: Stock OUT (sale) transaction bhi insert kar rahe hain
                    # Pehle stock_items table se item_id nikalain
                    try:
                        size_mm = int(item['size'].split('mm')[0].strip()) if 'mm' in item['size'] else 0
                        size_yard = int(item['size'].split('x')[1].split('Yard')[0].strip()) if 'x' in item['size'] and 'Yard' in item['size'] else 0
                        mic_val = int(item['mic']) if item['mic'] else 0
                    except Exception as e:
                        print(f"[DEBUG] Size parse error: {item['size']}, mic: {item['mic']}, error: {e}")
                        size_mm = 0
                        size_yard = 0
                        mic_val = 0
                    cursor.execute("""
                        SELECT id FROM stock_items WHERE size_mm = ? AND size_yard = ? AND color = ? AND brand = ? AND micron = ?
                    """, (
                        size_mm,
                        size_yard,
                        item['colour'],
                        item['brand'],
                        mic_val
                    ))
                    stock_item = cursor.fetchone()
                    print(f"[DEBUG] Bill item: {item}, resolved stock_item: {stock_item}")
                    if stock_item:
                        item_id = stock_item[0]
                        cursor.execute("""
                            INSERT INTO stock_transactions (
                                item_id, transaction_date, transaction_type, quantity, reference_id
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (
                            item_id,
                            bill_data['date'],
                            'sale',
                            int(item['qty']) if item['qty'] else 0,
                            bill_data['bill_no']
                        ))
                        print(f"[DEBUG] OUT entry inserted for item_id {item_id}, qty {item['qty']}")
                    else:
                        # Roman Urdu: Agar item nahi mila to naya item stock_items mai insert karo
                        cursor.execute("""
                            INSERT INTO stock_items (size_mm, size_yard, color, brand, micron)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            size_mm,
                            size_yard,
                            item['colour'],
                            item['brand'],
                            mic_val
                        ))
                        item_id = cursor.lastrowid
                        print(f"[DEBUG] New stock_item inserted: {item}, item_id: {item_id}")
                        cursor.execute("""
                            INSERT INTO stock_transactions (
                                item_id, transaction_date, transaction_type, quantity, reference_id
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (
                            item_id,
                            bill_data['date'],
                            'sale',
                            int(item['qty']) if item['qty'] else 0,
                            bill_data['bill_no']
                        ))
                        print(f"[DEBUG] OUT entry inserted for new item_id {item_id}, qty {item['qty']}")
            
            conn.commit()
            
            # Format date for display
            try:
                display_date = datetime.strptime(bill_data['date'], '%Y-%m-%d').strftime('%d/%m/%Y')
                bill_data['date'] = display_date
            except:
                bill_data['date'] = datetime.now().strftime('%d/%m/%Y')
            
            return render_template('bill_format.html', bill=bill_data)
            
        except Exception as e:
            print(f"Bill generation error: {e}")
            if 'conn' in locals():
                conn.rollback()
            flash('Error generating bill', 'error')
            return redirect(url_for('reports.generate_bill'))
            
        finally:
            if 'conn' in locals():
                conn.close()
            
    # GET request - show form
    today = datetime.now().strftime('%Y-%m-%d')
    next_bill_no = get_next_bill_number()  # Get auto-generated bill number
    return render_template('generate_bill.html', today=today, next_bill_no=next_bill_no)

@bp.route('/bills')
def list_bills():
    """List all bills with search"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Sab bills le kar aaen
        cursor.execute("""
            SELECT bill_no, date, customer_name 
            FROM bills 
            ORDER BY date DESC
        """)
        bills_raw = cursor.fetchall()
        bills = []
        for row in bills_raw:
            bill_no = row[0]
            # Har bill ki items ki QTY nikalain
            cursor.execute("""
                SELECT qty, per_ctn_qty FROM bill_items WHERE bill_no = ?
            """, (bill_no,))
            items = cursor.fetchall()
            total_qty = 0
            total_ctn = 0
            total_loose = 0
            # Roman Urdu: Yahan har item ki QTY ko CTN aur ROLL mai convert kar rahe hain
            for item in items:
                qty = int(item[0]) if item[0] else 0
                per_ctn_qty = int(item[1]) if item[1] else 0
                if per_ctn_qty > 0:
                    total_ctn += qty // per_ctn_qty
                    total_loose += qty % per_ctn_qty
                else:
                    total_loose += qty
            # Roman Urdu: Display string bana rahe hain
            if total_ctn > 0 and total_loose > 0:
                qty_display = f"{total_ctn} CTN + {total_loose} ROLL"
            elif total_ctn > 0:
                qty_display = f"{total_ctn} CTN"
            elif total_loose > 0:
                qty_display = f"{total_loose} ROLL"
            else:
                qty_display = "-"
            # Roman Urdu: Date ko DD-MM-YYYY format mein convert kar rahe hain
            date_val = row[1]
            try:
                if date_val and '-' in date_val:
                    date_obj = datetime.strptime(date_val, '%Y-%m-%d')
                    date_str = date_obj.strftime('%d-%m-%Y')
                else:
                    date_str = date_val
            except Exception:
                date_str = date_val
            bills.append({
                'bill_no': row[0],
                'date': date_str,
                'customer_name': row[2],
                'qty_display': qty_display
            })
        return render_template('bills_list.html', bills=bills)
    except Exception as e:
        print(f"Error listing bills: {e}")
        return render_template('bills_list.html', bills=[])
    finally:
        if conn:
            conn.close()

@bp.route('/api/bills/search')
def search_bills():
    """Search bills"""
    try:
        search = request.args.get('term', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT bill_no, date, customer_name 
            FROM bills 
            WHERE bill_no LIKE ? 
            OR customer_name LIKE ? 
            ORDER BY date DESC 
            LIMIT 10
        """, (f'%{search}%', f'%{search}%'))
        
        bills = [{
            'bill_no': row[0],
            'date': row[1],
            'customer_name': row[2]
        } for row in cursor.fetchall()]
        
        return jsonify(bills)
        
    except Exception as e:
        print(f"Bill search error: {e}")
        return jsonify([])
        
    finally:
        if conn:
            conn.close()

@bp.route('/bills/<bill_no>')
def view_bill(bill_no):
    """View bill details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get bill header
        cursor.execute("""
            SELECT bill_no, date, customer_name 
            FROM bills 
            WHERE bill_no = ?
        """, (bill_no,))
        
        bill = cursor.fetchone()
        if not bill:
            flash('Bill not found', 'error')
            return redirect(url_for('reports.list_bills'))
            
        # Get bill items
        cursor.execute("""
            SELECT qty, size, colour, brand, mic, printed, varity, per_ctn_qty, rate 
            FROM bill_items 
            WHERE bill_no = ?
        """, (bill_no,))
        
        rows = cursor.fetchall()
        items = []
        for row in rows:
            qty = int(row[0]) if row[0] else 0
            per_ctn_qty = int(row[7]) if row[7] else 0
            cartons = qty // per_ctn_qty if per_ctn_qty > 0 else 0
            loose = qty % per_ctn_qty if per_ctn_qty > 0 else qty
            # Qty display string
            if per_ctn_qty > 0:
                if loose == 0:
                    qty_display = f"{cartons} CTN"
                else:
                    qty_display = f"{cartons} CTN + {loose} ROLL" if cartons > 0 else f"{loose} ROLL"
            else:
                qty_display = f"{qty} ROLL"
            items.append({
                'qty': row[0],
                'size': row[1],
                'colour': row[2],
                'brand': row[3],
                'mic': row[4],
                'printed': row[5],
                'varity': row[6],
                'per_ctn_qty': row[7],
                'rate': row[8],
                'cartons': cartons,
                'loose': loose,
                'qty_display': qty_display
            })
        
        bill_data = {
            'bill_no': bill[0],
            'date': bill[1],
            'customer_name': bill[2],
            'items': items
        }
        
        return render_template('bill_format.html', bill=bill_data)
        
    except Exception as e:
        print(f"Error viewing bill: {e}")
        flash('Error viewing bill', 'error')
        return redirect(url_for('reports.list_bills'))
        
    finally:
        if conn:
            conn.close() 

@bp.route('/bills/edit/<bill_no>', methods=['GET', 'POST'])
def edit_bill(bill_no):
    # Roman Urdu: Bill edit karne ka route
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if request.method == 'POST':
            # Roman Urdu: Form se data le kar update karen
            customer_name = request.form.get('customer_name')
            date = request.form.get('date')
            if not date:
                flash('Date is required', 'error')
                return redirect(url_for('reports.edit_bill', bill_no=bill_no))
            date_val = date
            items_json = request.form.get('items')
            if not items_json:
                flash('No items data received', 'error')
                return redirect(url_for('reports.edit_bill', bill_no=bill_no))
            try:
                items = json.loads(items_json)
            except json.JSONDecodeError:
                flash('Invalid items data format', 'error')
                return redirect(url_for('reports.edit_bill', bill_no=bill_no))
            # Roman Urdu: Bill update karo
            cursor.execute("UPDATE bills SET customer_name = ?, date = ? WHERE bill_no = ?", 
                         (customer_name, date_val, bill_no))
            # Roman Urdu: Bill items update karne ke liye pehle delete karo, phir naya insert karo
            cursor.execute("DELETE FROM bill_items WHERE bill_no = ?", (bill_no,))
            # Roman Urdu: Stock transactions se bhi purani sales delete karo
            cursor.execute("DELETE FROM stock_transactions WHERE reference_id = ? AND transaction_type = 'sale'", (bill_no,))
            # Roman Urdu: Naye items insert karo
            for item in items:
                if item.get('qty') and item.get('size'):
                    cursor.execute("""
                        INSERT INTO bill_items (bill_no, qty, size, colour, brand, mic, printed, varity, per_ctn_qty, rate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bill_no,
                        item.get('qty', 0),
                        item.get('size', ''),
                        item.get('colour', ''),
                        item.get('brand', ''),
                        item.get('mic', ''),
                        item.get('printed', ''),
                        item.get('varity', ''),
                        item.get('per_ctn_qty', 0),
                        item.get('rate', 0)
                    ))
                    # Roman Urdu: Stock OUT (sale) transaction bhi insert karo
                    try:
                        size_mm = int(item['size'].split('mm')[0].strip()) if 'mm' in item['size'] else 0
                        size_yard = int(item['size'].split('x')[1].split('Yard')[0].strip()) if 'x' in item['size'] and 'Yard' in item['size'] else 0
                        mic_val = int(item['mic']) if item['mic'] else 0
                    except Exception as e:
                        print(f"[DEBUG] Size parse error: {item['size']}, mic: {item['mic']}, error: {e}")
                        size_mm = 0
                        size_yard = 0
                        mic_val = 0
                    cursor.execute("""
                        SELECT id FROM stock_items WHERE size_mm = ? AND size_yard = ? AND color = ? AND brand = ? AND micron = ?
                    """, (
                        size_mm,
                        size_yard,
                        item['colour'],
                        item['brand'],
                        mic_val
                    ))
                    stock_item = cursor.fetchone()
                    if stock_item:
                        item_id = stock_item[0]
                    else:
                        cursor.execute("""
                            INSERT INTO stock_items (size_mm, size_yard, color, brand, micron)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            size_mm,
                            size_yard,
                            item['colour'],
                            item['brand'],
                            mic_val
                        ))
                        item_id = cursor.lastrowid
                    cursor.execute("""
                        INSERT INTO stock_transactions (
                            item_id, transaction_date, transaction_type, quantity, reference_id
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        item_id,
                        date_val,
                        'sale',
                        int(item['qty']) if item['qty'] else 0,
                        bill_no
                    ))
            conn.commit()
            flash(f'Bill {bill_no} updated successfully!', 'success')
            return redirect(url_for('reports.list_bills'))
            
        # GET request: Bill data la kar form show karo
        cursor.execute("SELECT bill_no, date, customer_name FROM bills WHERE bill_no = ?", (bill_no,))
        bill = cursor.fetchone()
        if not bill:
            flash('Bill not found', 'error')
            return redirect(url_for('reports.list_bills'))
            
        cursor.execute("SELECT qty, size, colour, brand, mic, printed, varity, per_ctn_qty, rate FROM bill_items WHERE bill_no = ?", (bill_no,))
        rows = cursor.fetchall()
        items = []
        for row in rows:
            items.append({
                'qty': row[0],
                'size': row[1],
                'colour': row[2],
                'brand': row[3],
                'mic': row[4],
                'printed': row[5],
                'varity': row[6],
                'per_ctn_qty': row[7],
                'rate': row[8]
            })
            
        bill_data = {
            'bill_no': bill[0],
            'date': bill[1],
            'customer_name': bill[2],
            'items': items
        }
        return render_template('edit_bill.html', bill=bill_data)
        
    except Exception as e:
        print(f"Error editing bill: {e}")
        flash('Error editing bill', 'error')
        return redirect(url_for('reports.list_bills'))
    finally:
        if 'conn' in locals():
            conn.close()

@bp.route('/bills/delete/<bill_no>', methods=['GET', 'POST'])
def delete_bill(bill_no):
    # Roman Urdu: Bill delete karne ka route
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Pehle bill items delete karo
        cursor.execute("DELETE FROM bill_items WHERE bill_no = ?", (bill_no,))
        # Stock transactions se bhi sales delete karo
        cursor.execute("DELETE FROM stock_transactions WHERE reference_id = ? AND transaction_type = 'sale'", (bill_no,))
        # Phir bill delete karo
        cursor.execute("DELETE FROM bills WHERE bill_no = ?", (bill_no,))
        conn.commit()
        # Roman Urdu: Delete ke baad bills list par redirect kar rahe hain
        return redirect(url_for('reports.list_bills'))
    except Exception as e:
        print(f"Error deleting bill: {e}")
        if 'conn' in locals():
            conn.rollback()
        # Roman Urdu: Agar error aaye to bills list par error message ke sath bhej dein
        return redirect(url_for('reports.list_bills'))
    finally:
        if 'conn' in locals():
            conn.close() 

@bp.route('/jumbo_stock_report')
def jumbo_stock_report():
    """Roman Urdu: Jambo Stock Report - har group ke liye unused aur loose count"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Roman Urdu: Saare jambos nikal lo, closed bhi aur active bhi
        cursor.execute('''
            SELECT j.jambo_no, j.colour, j.micron, j.size_mm, j.size_meter, j.balance_yard, j.calculated_yard, c.jambo_id
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
        ''')
        rows = cursor.fetchall()
        # Roman Urdu: Group by (colour, micron, size_mm)
        groups = defaultdict(lambda: {'full': 0, 'loose': 0, 'size_meter': None})
        for row in rows:
            colour = row[1]
            micron = row[2]
            size_mm = row[3]
            size_meter = row[4]
            balance_yard = row[5]
            calculated_yard = row[6]
            closed = row[7] is not None
            key = (colour, micron, size_mm)
            # Roman Urdu: Full unused (balance == calculated, not closed)
            if not closed and balance_yard == calculated_yard:
                groups[key]['full'] += 1
            # Roman Urdu: Loose (balance < calculated, not closed)
            elif not closed and balance_yard < calculated_yard and balance_yard > 0:
                groups[key]['loose'] += 1
            groups[key]['size_meter'] = size_meter
        # Roman Urdu: Data ko list bana lo template ke liye
        report_data = []
        for (colour, micron, size_mm), val in groups.items():
            report_data.append({
                'colour': colour,
                'micron': micron,
                'size_mm': size_mm,
                'size_meter': val['size_meter'],
                'full': val['full'],
                'loose': val['loose']
            })
        conn.close()
        return render_template('jumbo_stock_report.html', report_data=report_data)
    except Exception as e:
        print(f"Error generating jumbo stock report: {e}")
        return "Error generating report" 

@bp.route('/sales_report', methods=['GET', 'POST'])
def sales_report():
    """Roman Urdu: Sales Report - filters: customer, date, item"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Roman Urdu: Customers nikalne ke liye parties aur customer_orders dono table check karo
    cursor.execute("SELECT name FROM parties WHERE LOWER(party_type)='customer' ORDER BY name")
    party_customers = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT DISTINCT customer_name FROM customer_orders WHERE customer_name IS NOT NULL AND customer_name != ''")
    order_customers = set(row[0] for row in cursor.fetchall())
    parties = sorted(party_customers.union(order_customers))
    # Roman Urdu: Sab items nikal lo (unique size+colour+micron)
    cursor.execute("SELECT DISTINCT size, colour, mic FROM bill_items ORDER BY size, colour, mic")
    items = [f"{row[0]} | {row[1]} | {row[2]}" for row in cursor.fetchall()]
    sales_data = []
    filters = {'parties': [], 'items_list': [], 'date_from': '', 'date_to': ''}
    if request.method == 'POST':
        # Roman Urdu: Filters form se lo
        filters['parties'] = request.form.getlist('parties')
        filters['items_list'] = request.form.getlist('items')
        filters['date_from'] = request.form.get('date_from')
        filters['date_to'] = request.form.get('date_to')
        # Fix: Agar parties string hai, to list bana lo
        if isinstance(filters['parties'], str):
            filters['parties'] = [filters['parties']]
        # Roman Urdu: Sales data (bills/bill_items)
        base_query = '''
            SELECT b.date, b.customer_name, i.size, i.colour, i.mic, i.qty, i.rate, 'Sale' as type
            FROM bills b
            JOIN bill_items i ON b.bill_no = i.bill_no
            WHERE 1=1
        '''
        query_parts = []
        params = []
        # Roman Urdu: Sirf tab IN lagao jab parties empty na ho
        if filters['parties'] and len(filters['parties']) > 0:
            query_parts.append('b.customer_name IN (%s)' % (','.join(['?']*len(filters['parties']))))
            params += filters['parties']
        # Roman Urdu: Item filter ko robust bana rahe hain
        item_filters = []
        clean_items = filters.get('items_list', [])
        clean_items = [item for item in clean_items if item and item.strip()]
        for item in clean_items:
            parts = item.split('|')
            if len(parts) != 3:
                continue
            size, colour, mic = [x.strip().lower().replace('mm','').replace('yard','').replace('x','').replace(' ','') for x in parts]
            item_filters.append("(REPLACE(LOWER(REPLACE(REPLACE(i.size, 'mm', ''), 'yard', ''), ' ')), 'x', '') LIKE ? AND LOWER(REPLACE(i.colour, ' ', ''))=? AND LOWER(REPLACE(i.mic, ' ', ''))=?)")
            params += [f"%{size}%", colour, mic]
        if len(item_filters) > 0:
            query_parts.append('(' + ' OR '.join(item_filters) + ')')
        if query_parts:
            query = base_query + ' AND ' + ' AND '.join(query_parts)
        else:
            query = base_query
        cursor.execute(query, params)
        sales_data = list(cursor.fetchall())
        # Remove purchase rows, sirf sale rows dikhayein
        # sales_data += purchases  # <-- is line ko hata dein
    conn.close()
    return render_template('sales_report.html', parties=parties, items=items, sales_data=sales_data, filters=filters) 

@bp.route('/api/party_items', methods=['POST'])
def api_party_items():
    # Roman Urdu: Selected parties ke items la kar do (sales + purchases)
    data = request.get_json()
    parties = data.get('parties', [])
    conn = get_db_connection()
    cursor = conn.cursor()
    items = set()
    if parties:
        # Sales items (bill_items)
        query1 = '''
            SELECT DISTINCT i.size, i.colour, i.mic
            FROM bills b
            JOIN bill_items i ON b.bill_no = i.bill_no
            WHERE b.customer_name IN (%s)
        ''' % (','.join(['?']*len(parties)))
        cursor.execute(query1, parties)
        for row in cursor.fetchall():
            items.add(f"{row[0]} | {row[1]} | {row[2]}")
        # Purchases (jambo_rolls)
        query2 = '''
            SELECT DISTINCT size_mm, colour, micron
            FROM jambo_rolls
            WHERE party_name IN (%s)
        ''' % (','.join(['?']*len(parties)))
        cursor.execute(query2, parties)
        for row in cursor.fetchall():
            items.add(f"{row[0]}mm | {row[1]} | {row[2]}")
    else:
        # All sales items
        cursor.execute('SELECT DISTINCT size, colour, mic FROM bill_items')
        for row in cursor.fetchall():
            items.add(f"{row[0]} | {row[1]} | {row[2]}")
        # All purchases
        cursor.execute('SELECT DISTINCT size_mm, colour, micron FROM jambo_rolls')
        for row in cursor.fetchall():
            items.add(f"{row[0]}mm | {row[1]} | {row[2]}")
    conn.close()
    return jsonify({'items': sorted(items)}) 

@bp.route('/sales_purchase_reports')
def sales_purchase_reports():
    # Roman Urdu: Sales & Purchase Reports ka landing page
    return render_template('sales_purchase_reports.html') 

@bp.route('/purchase_report', methods=['GET', 'POST'])
def purchase_report():
    # Roman Urdu: Purchase Report - party filter mai sirf suppliers dikhana hai
    conn = get_db_connection()
    cursor = conn.cursor()
    # Sirf suppliers nikal lo
    cursor.execute("SELECT name FROM parties WHERE party_type='Supplier' ORDER BY name")
    parties = [row[0] for row in cursor.fetchall()]
    # Items (unique size+colour+micron from jambo_rolls)
    cursor.execute("SELECT DISTINCT size_mm, colour, micron FROM jambo_rolls ORDER BY size_mm, colour, micron")
    items = [f"{row[0]}mm | {row[1]} | {row[2]}" for row in cursor.fetchall()]
    purchase_data = []
    filters = {'parties': [], 'items_list': [], 'date_from': '', 'date_to': ''}
    if request.method == 'POST':
        filters['parties'] = request.form.getlist('parties')
        filters['items_list'] = request.form.getlist('items')
        filters['date_from'] = request.form.get('date_from')
        filters['date_to'] = request.form.get('date_to')
        # Purchases (jambo_rolls)
        query = '''
            SELECT date, party_name, (CAST(size_mm AS TEXT) || 'mm x ' || CAST(size_meter AS TEXT) || ' Yard') as size, colour, micron, net_weight, 'Purchase' as type
            FROM jambo_rolls
            WHERE 1=1
        '''
        params = []
        if filters['parties']:
            query += ' AND party_name IN (%s)' % (','.join(['?']*len(filters['parties'])))
            params += filters['parties']
        if filters['items_list']:
            item_filters = []
            for item in filters['items_list']:
                if item and item.strip():
                    parts = item.split('|')
                    if len(parts) != 3:
                        continue
                    size, colour, mic = [x.strip().replace('mm','').replace('Yard','').replace('x','x').replace(' ','') for x in parts]
                    item_filters.append('(CAST(size_mm AS TEXT) LIKE ? AND colour=? AND CAST(micron AS TEXT)=?)')
                    params += [f"%{size}%", colour, mic]
            query += ' AND (' + ' OR '.join(item_filters) + ')'
        if filters['date_from']:
            query += ' AND date >= ?'
            params.append(filters['date_from'])
        if filters['date_to']:
            query += ' AND date <= ?'
            params.append(filters['date_to'])
        query += ' ORDER BY date DESC'
        cursor.execute(query, params)
        purchase_data = cursor.fetchall()
    conn.close()
    return render_template('purchase_report.html', parties=parties, items=items, purchase_data=purchase_data, filters=filters) 

@bp.route('/api/purchase_items/search')
def search_purchase_items():
    """Search purchase items for autocomplete (stock search ki tarah)"""
    try:
        search = request.args.get('term', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        # Search in jambo_rolls for items
        cursor.execute("""
            SELECT DISTINCT size_mm, colour, micron
            FROM jambo_rolls
            WHERE LOWER(CAST(size_mm AS TEXT)) LIKE LOWER(?)
            OR LOWER(colour) LIKE LOWER(?)
            OR LOWER(micron) LIKE LOWER(?)
            ORDER BY size_mm, colour, micron
            LIMIT 10
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))
        items = []
        for row in cursor.fetchall():
            items.append({
                'label': f"{row[0]}mm | {row[1]} | {row[2]}",
                'value': f"{row[0]}mm | {row[1]} | {row[2]}"
            })
        return jsonify(items)
    except Exception as e:
        print(f"Purchase item search error: {e}")
        return jsonify([])
    finally:
        if conn:
            conn.close() 