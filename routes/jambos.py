"""
Jambo management routes
"""
from flask import Blueprint, render_template, request, jsonify, make_response, send_file
from database import get_db_connection
from datetime import datetime, timedelta
import io

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

bp = Blueprint('jambos', __name__)

@bp.route('/api/challans/search', methods=['POST'])
def search_challans():
    """Search challans with filters"""
    try:
        print("🔍 Search challans API called")
        filters = request.get_json()
        
        if not filters:
            filters = {}
            
        print(f"🔍 Search filters: {filters}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if we have any data
        cursor.execute("SELECT COUNT(*) FROM jambo_rolls")
        total_count = cursor.fetchone()[0]
        print(f"📊 Total records in database: {total_count}")
        
        if total_count == 0:
            print("❌ No records found in database")
            return jsonify({
                'success': True,
                'challans': [],
                'message': 'No records found in database'
            })
        
        # Base query
        query = """
            SELECT 
                challan_no,
                date,
                party_name,
                COUNT(*) as total_items,
                SUM(net_weight) as total_weight
            FROM jambo_rolls 
            WHERE 1=1
        """
        params = []
        
        # Add filters
        if filters.get('challan_no'):
            query += " AND challan_no LIKE ?"
            params.append(f"%{filters['challan_no']}%")
        
        if filters.get('party_name'):
            query += " AND LOWER(party_name) LIKE LOWER(?)"
            params.append(f"%{filters['party_name']}%")
            
        # Handle date filters
        date_from = convert_date_format(filters.get('date_from'))
        date_to = convert_date_format(filters.get('date_to'))
        
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
            print(f"📅 Filtering from date: {date_from}")
            
        if date_to:
            # Add one day to include the end date
            date_obj = datetime.strptime(date_to, '%Y-%m-%d')
            next_day = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            query += " AND date < ?"
            params.append(next_day)
            print(f"📅 Filtering to date: {next_day}")
            
        # If no filters, limit to recent challans
        if not any([filters.get('challan_no'), filters.get('party_name'), date_from, date_to]):
            query += " AND date >= date('now', '-30 days')"
            print("📅 No filters applied, showing last 30 days")
        
        # Group by and order
        query += """
            GROUP BY challan_no, date, party_name
            ORDER BY date DESC, challan_no DESC
            LIMIT 50
        """
        
        print(f"🔍 Executing query: {query}")
        print(f"🔍 Parameters: {params}")
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        print(f"📊 Found {len(rows)} results")
        
        challans = []
        for row in rows:
            try:
                # Convert date to DD-MM-YYYY format for display
                date_obj = datetime.strptime(row[1], '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d-%m-%Y')
                
                challans.append({
                    'challan_no': row[0] or '',
                    'date': formatted_date,
                    'party_name': row[2] or '',
                    'total_items': row[3] or 0,
                    'total_weight': round(float(row[4] or 0), 2)
                })
            except Exception as e:
                print(f"❌ Error processing row {row}: {str(e)}")
                continue
        # Roman Urdu: Agar pehli query me result nahi aaya, to fallback query chalao
        if not challans:
            print("⚠️ No challans found with filters, trying fallback query (no filters)")
            cursor.execute("""
                SELECT 
                    challan_no,
                    date,
                    party_name,
                    COUNT(*) as total_items,
                    SUM(net_weight) as total_weight
                FROM jambo_rolls
                GROUP BY challan_no, date, party_name
                ORDER BY date DESC, challan_no DESC
                LIMIT 50
            """)
            rows = cursor.fetchall()
            for row in rows:
                try:
                    date_obj = datetime.strptime(row[1], '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d-%m-%Y')
                    challans.append({
                        'challan_no': row[0] or '',
                        'date': formatted_date,
                        'party_name': row[2] or '',
                        'total_items': row[3] or 0,
                        'total_weight': round(float(row[4] or 0), 2)
                    })
                except Exception as e:
                    print(f"❌ Error processing row {row}: {str(e)}")
                    continue
        
        return jsonify({
            'success': True,
            'challans': challans
        })
        
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error searching challans: {str(e)}'
        })
        
    finally:
        if conn:
            conn.close()

def convert_date_format(date_str):
    """Convert date string to YYYY-MM-DD format"""
    if not date_str:
        return None
        
    try:
        # Try different date formats
        for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y', '%d/%m/%y']:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
                
        # Try month-year format
        if len(date_str.split('-')) == 2 or len(date_str.split('/')) == 2:
            separator = '-' if '-' in date_str else '/'
            month, year = date_str.split(separator)
            if len(year) == 2:
                year = '20' + year
            # Convert to first day of month
            return f"{year}-{month.zfill(2)}-01"
            
        return None
    except:
        return None

@bp.route('/api/next-challan-number')
def get_next_challan_number():
    """Get next available challan number"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the highest challan number
        cursor.execute("SELECT challan_no FROM jambo_rolls WHERE challan_no LIKE 'CH-%' ORDER BY challan_no DESC LIMIT 1")
        result = cursor.fetchone()
        
        if result and result[0]:
            # Extract number from CH-XXXX format
            current_num = int(result[0].split('-')[1])
            next_num = current_num + 1
        else:
            next_num = 1
            
        # Format as CH-XXXX
        next_challan = f"CH-{str(next_num).zfill(4)}"
        
        return jsonify({
            'success': True,
            'next_challan_no': next_challan
        })
        
    except Exception as e:
        print(f"Error getting next challan number: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting next challan number: {str(e)}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/next-jambo-number')
def get_next_jambo_number():
    """Get next available jambo number"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the highest jambo number
        cursor.execute("SELECT MAX(jambo_no) FROM jambo_rolls")
        result = cursor.fetchone()
        # Agar database empty hai to 1000 return kare, warna max+1
        max_jambo = result[0] if result[0] else 1000
        next_number = max_jambo + 1
        # Roman Urdu: Ab Jambo No 1001 se start hoga
        print(f"Current max jambo: {max_jambo}, Next jambo: {next_number}")
        return jsonify({
            'success': True,
            'next_jambo_no': next_number
        })
        
    except Exception as e:
        print(f"Error getting next jambo number: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting next jambo number: {str(e)}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/jambos')
def list_jambos():
    """Jambo rolls listing page"""
    return render_template('jambos_list.html')

@bp.route('/jambos/excel-import')
def excel_import_page():
    """Excel import page for jambos"""
    return render_template('excel_import.html')

def generate_jambos_pdf(jambos, search='', jambo_no='', date_search='', color='', party=''):
    """Generate PDF with exact same format as desktop app"""
    try:
        # Get current timestamp for filename
        timestamp = datetime.now().strftime('%d%m%Y_%H%M')
        
        # Generate clean HTML with exact desktop format
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Jambo Report {timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: Arial, sans-serif; 
            padding: 20px; 
            background: #f5f5f5;
        }}
        
        .header {{ 
            background: #2c3e50; 
            color: white; 
            padding: 20px; 
            text-align: center; 
            margin-bottom: 25px;
            border-radius: 8px;
        }}
        .header h1 {{ 
            font-size: 22px; 
            font-weight: bold;
            margin: 0;
        }}
        
        .data-box {{
            background: white;
            border: 3px solid #34495e;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 12px;
        }}
        
        th {{ 
            background: #34495e; 
            color: white; 
            padding: 12px 8px; 
            text-align: center; 
            font-weight: bold;
            border: 1px solid #2c3e50;
        }}
        
        td {{ 
            padding: 10px 8px; 
            text-align: center; 
            border: 1px solid #ddd;
        }}
        
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:nth-child(odd) {{ background: white; }}
        
        .jambo-no {{ font-weight: bold; color: #2c3e50; }}
        .colour-cell {{ font-weight: bold; color: #e74c3c; }}
        
        @media print {{
            body {{ padding: 10px; background: white; }}
            .data-box {{ 
                border: 2px solid #34495e;
                box-shadow: none;
            }}
            th, td {{ padding: 8px 6px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 JAMBO ROLLS INVENTORY</h1>
    </div>
    
    <div class="data-box">
        <table>
            <thead>
                <tr>
                    <th>Jambo No</th>
                    <th>Date</th>
                    <th>Size</th>
                    <th>Colour</th>
                    <th>Micron</th>
                    <th>Roll No</th>
                    <th>Weight</th>
                    <th>Party</th>
                </tr>
            </thead>
            <tbody>'''
        
        # Add data rows with exact format
        for jambo in jambos:
            formatted_date = datetime.strptime(jambo[2], '%Y-%m-%d').strftime('%d-%m-%Y') if jambo[2] else ''
            size_display = f"{jambo[3]}mm x {jambo[4]:.0f}m"
            
            html_content += f'''
                <tr>
                    <td class="jambo-no">{jambo[1]}</td>
                    <td>{formatted_date}</td>
                    <td>{size_display}</td>
                    <td class="colour-cell">{jambo[5]}</td>
                    <td>{jambo[6]}</td>
                    <td>{jambo[7]}</td>
                    <td>{jambo[8]:.1f} kg</td>
                    <td>{jambo[9]}</td>
                </tr>'''
        
        html_content += '''
            </tbody>
        </table>
    </div>
</body>
</html>'''
        
        # Return HTML response that browser will convert to PDF
        response = make_response(html_content)
        filename = f"JAMBO_REPORT_{timestamp}.html"
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        print(f'Error generating PDF: {str(e)}')
        return redirect(url_for('jambos.list_jambos'))

@bp.route('/jambos/bulk', methods=['GET'])
def bulk_add_jambos():
    """Bulk Add Jambos page"""
    return render_template('bulk_add_jambos.html')

@bp.route('/api/jambos/bulk', methods=['POST'])
def api_save_bulk_jambos():
    """Save bulk jambos via API"""
    conn = None
    try:
        print("🔧 Bulk save API called")
        bulk_data = request.get_json()
        print(f"📦 Received bulk data: {bulk_data}")
        
        # Handle frontend's data structure
        if not bulk_data:
            print("❌ No data received")
            return jsonify({'success': False, 'error': 'No data received'})
        
        # Extract common data and jambos based on frontend structure
        common_data = bulk_data.get('common', {})
        jambos_list = bulk_data.get('jambos', [])
        
        if not jambos_list:
            print("❌ No jambos data found")
            return jsonify({'success': False, 'error': 'No jambos data received'})
        
        date = common_data.get('date')
        party_name = common_data.get('party')
        challan_no = common_data.get('challan', '')
        
        print(f"📝 Header data - Date: {date}, Party: {party_name}, Challan: {challan_no}")
        
        if not date or not party_name:
            print("❌ Missing required fields")
            return jsonify({'success': False, 'error': 'Date and Party Name are required'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            cursor.execute('BEGIN TRANSACTION')
            
            successful_entries = 0
            errors = []
            
            print(f"🔄 Processing {len(jambos_list)} jambos...")
            
            for jambo in jambos_list:
                try:
                    # Extract values with proper validation
                    jambo_no = int(jambo.get('jambo_no', 0))
                    size_mm = int(jambo.get('size_mm', 0))
                    size_meter = float(jambo.get('size_meter', 0))
                    colour = str(jambo.get('colour', 'Clear')).strip().upper()
                    micron = int(jambo.get('micron', 37))
                    roll_no = int(jambo.get('roll_no', 1))
                    net_weight = float(jambo.get('weight_kg', 0))
                    rate_kg = float(jambo.get('rate', 0))
                    
                    # Validate required fields
                    if not jambo_no or not size_mm or not size_meter:
                        raise ValueError("Missing required fields")
                    
                    # Calculate values
                    calculated_yard = round(size_meter * 1.08325)
                    actual_yard = calculated_yard  # Use calculated value directly
                    balance_yard = actual_yard
                    extra_yard = actual_yard - calculated_yard
                    amount = net_weight * rate_kg
                    
                    print(f"💾 Saving Jambo {jambo_no}: {size_mm}mm x {size_meter}m, {colour}")
                    
                    cursor.execute('''
                        INSERT INTO jambo_rolls (
                            jambo_no, date, size_mm, size_meter, colour, micron, 
                            roll_no, net_weight, party_name, calculated_yard, 
                            actual_yard, rate_kg, amount, balance_yard, extra_yard, 
                            challan_no
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        jambo_no, date, size_mm, size_meter, colour, micron,
                        roll_no, net_weight, party_name, calculated_yard,
                        actual_yard, rate_kg, amount, balance_yard, extra_yard,
                        challan_no
                    ))
                    
                    successful_entries += 1
                    print(f"✅ Jambo {jambo_no} saved successfully")
                    
                except Exception as e:
                    error_msg = f"Error saving jambo {jambo.get('jambo_no', 'Unknown')}: {str(e)}"
                    print(f"❌ {error_msg}")
                    errors.append(error_msg)
                    raise
            
            # Commit transaction
            cursor.execute('COMMIT')
            print(f"✅ Transaction committed successfully")
            
            return jsonify({
                'success': True, 
                'saved_count': successful_entries,
                'challan_no': challan_no,
                'party_name': party_name,
                'errors': len(errors),
                'error_details': errors[:3] if errors else []
            })
            
        except Exception as e:
            # Rollback on error
            cursor.execute('ROLLBACK')
            print(f"❌ Transaction rolled back due to error: {str(e)}")
            raise
            
    except Exception as e:
        print(f"❌ Bulk save error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/jambo/close/<int:jambo_no>', methods=['POST'])
def close_jambo(jambo_no):
    """Close a jambo (hide from production)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if jambo exists
        cursor.execute("SELECT * FROM jambo_rolls WHERE jambo_no = ?", (jambo_no,))
        jambo = cursor.fetchone()
        
        if not jambo:
            return jsonify({'success': False, 'message': 'Jambo not found!'})
        
        # Check if already closed
        cursor.execute("SELECT COUNT(*) FROM closed_jambos WHERE jambo_id = ?", (jambo_no,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Jambo already closed!'})
        
        # Close the jambo
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO closed_jambos (jambo_id, closed_date) VALUES (?, ?)", 
                      (jambo_no, current_date))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Jambo #{jambo_no} closed successfully!',
            'jambo_no': jambo_no,
            'status': 'CLOSED'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error closing jambo: {str(e)}'})

@bp.route('/api/jambo/reopen/<int:jambo_no>', methods=['POST'])
def reopen_jambo(jambo_no):
    """Reopen a closed jambo"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if jambo exists
        cursor.execute("SELECT * FROM jambo_rolls WHERE jambo_no = ?", (jambo_no,))
        jambo = cursor.fetchone()
        
        if not jambo:
            return jsonify({'success': False, 'message': 'Jambo not found!'})
        
        # Check if jambo is closed
        cursor.execute("SELECT COUNT(*) FROM closed_jambos WHERE jambo_id = ?", (jambo_no,))
        if cursor.fetchone()[0] == 0:
            return jsonify({'success': False, 'message': 'Jambo is not closed!'})
        
        # Reopen the jambo
        cursor.execute("DELETE FROM closed_jambos WHERE jambo_id = ?", (jambo_no,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Jambo #{jambo_no} reopened successfully!',
            'jambo_no': jambo_no,
            'status': 'ACTIVE'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error reopening jambo: {str(e)}'})

@bp.route('/api/jambo/status/<int:jambo_no>')
def get_jambo_status(jambo_no):
    """Get jambo status (ACTIVE/CLOSED)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if jambo is closed
        cursor.execute("SELECT closed_date FROM closed_jambos WHERE jambo_id = ?", (jambo_no,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'jambo_no': jambo_no,
                'status': 'CLOSED',
                'closed_date': result[0]
            })
        else:
            return jsonify({
                'success': True,
                'jambo_no': jambo_no,
                'status': 'ACTIVE'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting jambo status: {str(e)}'})

@bp.route('/api/jambo/production-check/<int:jambo_no>')
def check_jambo_production(jambo_no):
    """Check if jambo has production orders"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if jambo has production orders
        cursor.execute("SELECT COUNT(*) FROM production_orders WHERE jambo_no = ?", (jambo_no,))
        production_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'jambo_no': jambo_no,
            'has_production': production_count > 0,
            'production_count': production_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@bp.route('/api/challans/load/<challan_no>')
def load_challan(challan_no):
    """Load challan data for editing"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"🔍 Loading challan: {challan_no}")
        
        # Try to find by actual challan number first
        cursor.execute("""
            SELECT jambo_no, date, size_mm, size_meter, colour, micron, 
                   roll_no, net_weight, party_name, rate_kg, calculated_yard, challan_no
            FROM jambo_rolls 
            WHERE challan_no = ?
            ORDER BY jambo_no
        """, (challan_no,))
        
        rows = cursor.fetchall()
        
        # If not found by challan_no, try to parse generated identifier (CH-YYYY-MM-DD-XXX format)
        if not rows and challan_no.startswith('CH-'):
            try:
                # Extract date and party prefix from generated identifier
                parts = challan_no.split('-')
                if len(parts) >= 5:  # CH-YYYY-MM-DD-XXX
                    date_part = f"{parts[1]}-{parts[2]}-{parts[3]}"
                    party_prefix = parts[4]
                    
                    cursor.execute("""
                        SELECT jambo_no, date, size_mm, size_meter, colour, micron, 
                               roll_no, net_weight, party_name, rate_kg, calculated_yard, challan_no
                        FROM jambo_rolls 
                        WHERE date = ? AND SUBSTR(party_name, 1, 3) = ?
                        ORDER BY jambo_no
                    """, (date_part, party_prefix))
                    
                    rows = cursor.fetchall()
                    print(f"🔍 Found {len(rows)} rows by generated identifier")
            except Exception as e:
                print(f"🔍 Error parsing generated identifier: {e}")
        
        if not rows:
            conn.close()
            return jsonify({
                'success': False,
                'message': f'No data found for challan {challan_no}'
            })
        
        # Extract common data from first row
        first_row = rows[0]
        actual_challan = first_row[11] if first_row[11] else challan_no
        
        common_data = {
            'date': first_row[1],
            'party': first_row[8],
            'challan': actual_challan,
            'partyChallan': ''  # We don't store party challan in current schema
        }
        
        # Extract jambo items
        jambos = []
        for row in rows:
            jambos.append({
                'jambo_no': row[0],
                'size_mm': row[2],
                'size_meter': row[3],
                'colour': row[4],
                'micron': row[5],
                'roll_no': row[6],
                'weight_kg': row[7],
                'rate': row[9] if row[9] else 0,
                'calc_yard': row[10] if row[10] else 0
            })
        
        conn.close()
        
        print(f"✅ Loaded {len(jambos)} jambos for challan {challan_no}")
        
        return jsonify({
            'success': True,
            'challan_data': {
                'common': common_data,
                'jambos': jambos
            }
        })
        
    except Exception as e:
        print(f"❌ Error loading challan: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@bp.route('/api/jambos/bulk/preview', methods=['POST'])
def preview_bulk_jambos():
    """Preview bulk jambos before saving"""
    try:
        data = request.get_json()
        common_data = data.get('common', {})
        jambos = data.get('jambos', [])
        
        if not jambos:
            return jsonify({
                'success': False,
                'message': 'No jambos to preview'
            })
        
        # Group jambos by micron and colour with weight breakdown
        grouped_jambos = {}
        grand_total_weight = 0
        
        for jambo in jambos:
            try:
                micron = int(jambo.get('micron', 37))
                colour = jambo.get('colour', 'Clear').upper()
                weight = float(jambo.get('weight_kg', 0))
                
                key = f"{micron}mic {colour}"
                
                if key not in grouped_jambos:
                    grouped_jambos[key] = {
                        'micron': micron,
                        'colour': colour,
                        'count': 0,
                        'total_weight': 0,
                        'weight_breakdown': {},  # Track weight breakdown
                        'description': f"JAMBO ROLL - {micron} MIC / {colour}"
                    }
                
                # Track weight breakdown
                if weight not in grouped_jambos[key]['weight_breakdown']:
                    grouped_jambos[key]['weight_breakdown'][weight] = 0
                grouped_jambos[key]['weight_breakdown'][weight] += 1
                
                grouped_jambos[key]['count'] += 1
                grouped_jambos[key]['total_weight'] += weight
                grand_total_weight += weight
                
            except (ValueError, TypeError):
                continue
        
        # Update descriptions with weight breakdown
        for key, group in grouped_jambos.items():
            weight_parts = []
            for weight, count in sorted(group['weight_breakdown'].items(), reverse=True):
                if weight == int(weight):  # Show as integer if no decimal
                    weight_parts.append(f"{int(weight)}kg×{count}")
                else:
                    weight_parts.append(f"{weight}kg×{count}")
            
            weight_detail = " (" + ", ".join(weight_parts) + ")"
            group['description'] = f"JAMBO ROLL - {group['micron']} MIC / {group['colour']}{weight_detail}"
        
        # Convert to list for frontend
        grouped_items = list(grouped_jambos.values())
        
        return jsonify({
            'success': True,
            'preview_data': {
                'common': common_data,
                'jambos': jambos,
                'grouped_items': grouped_items,
                'grand_total_weight': round(grand_total_weight, 2),
                'total_items': len(jambos)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@bp.route('/api/jambos/bulk/pdf', methods=['POST'])
def generate_bulk_pdf():
    """Generate PDF for bulk challan"""
    try:
        if not PDF_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'PDF generation not available'
            })
        
        data = request.get_json()
        preview_data = data.get('preview_data', {})
        
        if not preview_data:
            return jsonify({
                'success': False,
                'message': 'No preview data provided'
            })
        
        # Create PDF in memory
        buffer = io.BytesIO()
        
        # Create the PDF document with A4 size and margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create content list
        content = []
        
        # Add title with larger font and more space
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=10*mm,
            textColor=colors.black
        )
        content.append(Paragraph('DELIVERY CHALLAN', title_style))
        
        # Add company name with medium size
        company_style = ParagraphStyle(
            'Company',
            parent=styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=15*mm,
            textColor=colors.black
        )
        content.append(Paragraph('Jambo Roll Manufacturing Company', company_style))
        
        # Format date in DD-MM-YYYY format
        date_str = preview_data.get('common', {}).get('date', '')
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d-%m-%Y')
        except:
            formatted_date = date_str
        
        # Add details with better alignment and bold labels
        common_data = preview_data.get('common', {})
        details = [
            [Paragraph('<b>Party:</b>', styles['Normal']), Paragraph(f"<b>{common_data.get('party', '')}</b>", styles['Normal'])],
            [Paragraph('<b>Date:</b>', styles['Normal']), formatted_date],
            [Paragraph('<b>Challan No:</b>', styles['Normal']), common_data.get('challan', '')]
        ]
        
        # Create details table with better spacing
        details_table = Table(details, colWidths=[25*mm, 155*mm])  # Adjusted column widths
        details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),   # Labels left aligned
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # Values left aligned
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2*mm),  # Reduced right padding
            ('LEFTPADDING', (0, 0), (-1, -1), 2*mm),   # Reduced left padding
        ]))
        content.append(details_table)
        content.append(Spacer(1, 10*mm))
        
        # Add items table with improved header and formatting
        items_data = [[
            Paragraph('<b><font color="white">S.No.</font></b>', styles['Normal']),
            Paragraph('<b><font color="white">Description</font></b>', styles['Normal']),
            Paragraph('<b><font color="white">Quantity</font></b>', styles['Normal']),
            Paragraph('<b><font color="white">Weight (Kg)</font></b>', styles['Normal'])
        ]]
        
        # Add items with proper formatting
        grouped_items = preview_data.get('grouped_items', [])
        for i, item in enumerate(grouped_items, 1):
            description = item.get('description', '').replace('JAMBO ROLL - ', '')  # Remove redundant text
            items_data.append([
                str(i),
                description,
                f"{item.get('count', 0)} Jambo",
                f"{item.get('total_weight', 0):.2f} KG"
            ])
        
        # Add total row with bold text
        grand_total = preview_data.get('grand_total_weight', 0)
        total_jambos = preview_data.get('total_items', 0)
        items_data.append([
            '',
            'Grand Total',
            f'{total_jambos} Jambo',
            f'{grand_total:.2f} KG'
        ])
        
        # Create items table with improved styling
        items_table = Table(items_data, colWidths=[20*mm, 100*mm, 30*mm, 30*mm])
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),  # Use bold font for all cells
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            # Header row styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Data rows alignment
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Sr. column
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Description column
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Quantity column
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),   # Weight column
            # Grid styling for data rows
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
            # Box around all rows including total
            ('BOX', (0, 0), (-1, -1), 2, colors.black),
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3*mm),
            # Alternating row colors
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
            # Total row styling
            ('GRID', (0, -1), (-1, -1), 2, colors.black),  # Thick grid for total row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0'))
        ]))
        content.append(items_table)
        
        # Build PDF
        doc.build(content)
        
        # Create response
        buffer.seek(0)
        
        # Generate filename
        party_name = common_data.get('party', 'Unknown').replace(' ', '_')
        challan_no = common_data.get('challan', 'Unknown')
        filename = f"Challan_{challan_no}_{party_name}.pdf"
        
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'PDF generation failed: {str(e)}'
        })

@bp.route('/api/jambos/active')
def get_active_jambos():
    """Get list of active jambos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active jambos (not closed)
        cursor.execute('''
            SELECT j.jambo_no, j.date, j.colour, j.micron, j.party_name,
                   j.size_mm, j.size_meter, j.balance_yard
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
            ORDER BY j.date DESC, j.jambo_no DESC
        ''')
        
        jambos = []
        for row in cursor.fetchall():
            jambos.append({
                'jambo_no': row[0],
                'date': row[1],
                'colour': row[2],
                'micron': row[3],
                'party_name': row[4],
                'size_mm': row[5],
                'size_meter': row[6],
                'balance_yard': row[7]
            })
        
        conn.close()
        return jsonify({'success': True, 'jambos': jambos})
        
    except Exception as e:
        print(f"Error getting active jambos: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/items/matching/<jambo_no>')
def get_matching_items(jambo_no):
    """Get items that match jambo specifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get jambo details
        cursor.execute('''
            SELECT colour, micron, size_mm
            FROM jambo_rolls
            WHERE jambo_no = ?
        ''', (jambo_no,))
        
        jambo = cursor.fetchone()
        if not jambo:
            return jsonify({'success': False, 'error': 'Jambo not found'})
            
        jambo_colour = jambo[0]
        jambo_micron = jambo[1]
        jambo_width = jambo[2]
        
        # Get matching items from active orders
        cursor.execute('''
            SELECT i.item_id, i.order_no, i.size, i.colour, i.micron,
                   i.qty, i.packing, o.customer_name as party_name,
                   COALESCE(SUM(p.produced_pieces), 0) as produced_pieces
            FROM order_items i
            INNER JOIN customer_orders o ON i.order_no = o.order_no
            LEFT JOIN production_orders p ON i.order_no = p.order_no AND i.item_id = p.item_id
            LEFT JOIN closed_order_items c ON i.order_no = c.order_no AND i.item_id = c.item_id
            WHERE i.colour = ? 
            AND i.micron = ?
            AND CAST(SUBSTR(i.size, 1, INSTR(i.size, 'mm')-1) AS INTEGER) <= ?
            AND o.status IN ('Pending', 'In Progress')
            AND c.item_id IS NULL
            GROUP BY i.item_id, i.order_no
            HAVING (
                CASE 
                    WHEN i.qty LIKE '%pcs%' THEN CAST(SUBSTR(i.qty, 1, INSTR(i.qty, 'pcs')-1) AS INTEGER)
                    WHEN i.qty LIKE '%ctn%' THEN CAST(SUBSTR(i.qty, 1, INSTR(i.qty, 'ctn')-1) AS INTEGER) * i.packing
                    ELSE CAST(i.qty AS INTEGER) * i.packing
                END
            ) > COALESCE(SUM(p.produced_pieces), 0)
            ORDER BY o.order_date ASC
        ''', (jambo_colour, jambo_micron, jambo_width))
        
        items = []
        for row in cursor.fetchall():
            # Calculate total and remaining pieces
            qty_str = str(row[5]).lower().strip()
            packing = int(row[6]) if row[6] else 48
            produced = int(row[8]) if row[8] else 0
            
            if 'pcs' in qty_str:
                total_pieces = int(qty_str.split('pcs')[0])
            elif 'ctn' in qty_str:
                cartons = int(qty_str.split('ctn')[0])
                total_pieces = cartons * packing
            else:
                cartons = int(qty_str)
                total_pieces = cartons * packing
            
            remaining_pieces = total_pieces - produced
            
            if remaining_pieces > 0:
                items.append({
                    'item_id': row[0],
                    'order_no': row[1],
                    'size': row[2],
                    'colour': row[3],
                    'micron': row[4],
                    'total_pieces': total_pieces,
                    'produced_pieces': produced,
                    'remaining_pieces': remaining_pieces,
                    'party_name': row[7]
                })
        
        conn.close()
        return jsonify({'success': True, 'items': items})
        
    except Exception as e:
        print(f"Error getting matching items: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/jambos/data')
def get_jambos_data():
    """Get list of all jambos"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all jambos with production data
        cursor.execute("""
            SELECT j.*,
                   COALESCE(SUM(po.yards_used), 0) as used_yards,
                   CASE WHEN c.jambo_id IS NOT NULL THEN 'CLOSED' ELSE 'ACTIVE' END as status
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            LEFT JOIN production_orders po ON j.jambo_no = po.jambo_no
            GROUP BY j.jambo_no, j.date, j.size_mm, j.size_meter, j.colour, j.micron, 
                     j.roll_no, j.net_weight, j.party_name, j.rate_kg, j.calculated_yard,
                     j.balance_yard, j.extra_yard
            ORDER BY j.date DESC, j.jambo_no DESC
        """)
        
        jambos = cursor.fetchall()
        print(f"🔍 DEBUG: Found {len(jambos)} jambos")
        
        # Convert to list of dicts
        jambos_list = []
        for jambo in jambos:
            # Get actual production data
            used_yards = jambo[-2] if jambo[-2] else 0
            
            # Use actual balance from database, don't recalculate
            balance = jambo[14] if jambo[14] else 0  # balance_yard from jambo_rolls
            if balance < 0:
                balance = 0
                
            jambos_list.append({
                'jambo_no': jambo[1],
                'date': jambo[2],
                'size_mm': jambo[3],
                'size_meter': jambo[4],
                'colour': jambo[5],
                'micron': jambo[6],
                'roll_no': jambo[7],
                'net_weight': jambo[8],
                'party_name': jambo[9],
                'rate_kg': jambo[10],
                'calculated_yard': jambo[11] if jambo[11] else 0,
                'balance_yard': balance,
                'extra_yard': jambo[15] if jambo[15] else 0,
                'used_yards': used_yards,
                'status': jambo[-1]
            })
        
        conn.close()
        print(f"🔍 DEBUG: Returning {len(jambos_list)} jambos")
        
        return jsonify({
            'success': True,
            'jambos': jambos_list
        })
        
    except Exception as e:
        print(f"❌ ERROR in get_jambos_data: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'message': f'Error getting jambos: {str(e)}'
        }) 

@bp.route('/api/parties/list')
def get_parties_list():
    """Get list of suppliers"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get only suppliers from parties table
        cursor.execute("""
            SELECT DISTINCT name 
            FROM parties 
            WHERE party_type = 'supplier' 
            AND is_active = 1 
            AND name IS NOT NULL 
            AND name != ''
            ORDER BY name
        """)
        
        parties = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'parties': parties
        })
        
    except Exception as e:
        print(f"Error getting suppliers: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error getting suppliers: {str(e)}'
        })
        
    finally:
        if conn:
            conn.close()

@bp.route('/api/jambos/excel-import', methods=['POST'])
def excel_import_jambos():
    """Import jambos from Excel file"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file uploaded'
            })
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            })
            
        # Read Excel file
        import pandas as pd
        df = pd.read_excel(file)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Extract data from Excel row
                jambo_no = int(row.get('jambo_no', 0))
                date = str(row.get('date', ''))
                size_mm = int(row.get('size_mm', 0))
                size_meter = float(row.get('size_meter', 0))
                colour = str(row.get('colour', ''))
                micron = int(row.get('micron', 37))
                roll_no = int(row.get('roll_no', 1))
                net_weight = float(row.get('net_weight', 0))
                party_name = str(row.get('party_name', ''))
                calculated_yard = int(row.get('calculated_yard', 0))
                actual_yard = int(row.get('actual_yard', 0))
                rate_kg = float(row.get('rate_kg', 0))
                amount = float(row.get('amount', 0))
                balance_yard = int(row.get('balance_yard', 0))
                
                # Insert jambo
                cursor.execute('''
                    INSERT OR IGNORE INTO jambo_rolls (
                        jambo_no, date, size_mm, size_meter, colour, micron, roll_no,
                        net_weight, party_name, calculated_yard, actual_yard, rate_kg,
                        amount, balance_yard
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (jambo_no, date, size_mm, size_meter, colour, micron, roll_no,
                      net_weight, party_name, calculated_yard, actual_yard, rate_kg,
                      amount, balance_yard))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {index + 1}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {success_count} jambos. {error_count} errors.',
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        })
        
    except Exception as e:
        print(f"Error importing Excel: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error importing Excel: {str(e)}'
        })

@bp.route('/api/parties/add', methods=['POST'])
def add_party():
    """Add new party"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        party_type = data.get('party_type', 'supplier').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        address = data.get('address', '').strip()
        city = data.get('city', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'Party name is required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if party already exists
        cursor.execute("SELECT id FROM parties WHERE name = ?", (name,))
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Party with this name already exists'
            })
        
        # Insert new party
        cursor.execute('''
            INSERT INTO parties (name, party_type, phone, email, address, city)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, party_type, phone, email, address, city))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Party added successfully'
        })
        
    except Exception as e:
        print(f"Error adding party: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error adding party: {str(e)}'
        })

@bp.route('/api/challans/update', methods=['POST'])
def update_challan():
    """Update challan data"""
    try:
        data = request.get_json()
        print(f"🔍 Update challan received data: {data}")
        
        # Extract common data and jambos from frontend structure
        common_data = data.get('common', {})
        jambos = data.get('jambos', [])
        
        # Get challan number from common data
        original_challan = common_data.get('original_challan')
        new_challan = common_data.get('challan')
        
        print(f"📝 Original challan: {original_challan}, New challan: {new_challan}")
        
        if not original_challan:
            return jsonify({
                'success': False,
                'message': 'Original challan number is required for update'
            })
            
        if not new_challan:
            return jsonify({
                'success': False,
                'message': 'New challan number is required'
            })
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Begin transaction for update
        cursor.execute('BEGIN TRANSACTION')
        
        try:
            # Get all jambo data from common and individual jambo data
            date = common_data.get('date')
            party_name = common_data.get('party')
            # Roman Urdu: Agar date ya party_name empty hai to update na hone dein
            if not date or not party_name:
                cursor.execute('ROLLBACK')
                return jsonify({
                    'success': False,
                    'message': 'Date aur Party Name empty nahi ho sakte. Update fail.'
                })
            party_challan = common_data.get('partyChallan', '')
            
            print(f"🔄 Updating jambos with challan {original_challan} to {new_challan}")
            print(f"📝 Date: {date}, Party: {party_name}")
            
            updated_count = 0
            
            # Update each jambo with new data
            for jambo in jambos:
                jambo_no = jambo.get('jambo_no')
                if jambo_no:
                    # Convert jambo_no to int for database comparison
                    try:
                        jambo_no_int = int(jambo_no)
                    except (ValueError, TypeError):
                        print(f"⚠️  Invalid jambo_no: {jambo_no}")
                        continue
                    
                    # Update all jambo fields including challan number
                    cursor.execute('''
                        UPDATE jambo_rolls 
                        SET date = ?, 
                            party_name = ?,
                            challan_no = ?,
                            size_mm = ?,
                            size_meter = ?,
                            colour = ?,
                            micron = ?,
                            roll_no = ?,
                            net_weight = ?,
                            rate_kg = ?,
                            calculated_yard = ?,
                            amount = net_weight * rate_kg
                        WHERE jambo_no = ? AND challan_no = ?
                    ''', (
                        date,
                        party_name, 
                        new_challan,
                        jambo.get('size_mm'),
                        jambo.get('size_meter'),
                        jambo.get('colour', 'Clear'),
                        jambo.get('micron', 37),
                        jambo.get('roll_no', 1),
                        jambo.get('weight_kg', 0),
                        jambo.get('rate', 0),
                        jambo.get('calc_yard', 0),
                        jambo_no_int,  # Use integer version
                        original_challan
                    ))
                    
                    if cursor.rowcount > 0:
                        updated_count += 1
                        print(f"✅ Updated jambo {jambo_no}")
                    else:
                        print(f"⚠️  No update for jambo {jambo_no} - not found with challan {original_challan}")
            
            # Roman Urdu: Agar user sabhi jambos delete kar raha hai, to update na hone dein
            if not jambos:
                cursor.execute('ROLLBACK')
                return jsonify({
                    'success': False,
                    'message': 'Kam az kam ek jambo row zaroor honi chahiye. Sab jambos delete nahi kar sakte.'
                })
            
            # Purane jambos nikaalo (Roman Urdu: Pehle se maujood jambos ki list)
            cursor.execute("SELECT jambo_no FROM jambo_rolls WHERE challan_no = ?", (original_challan,))
            old_jambos = set(row[0] for row in cursor.fetchall())
            
            # Naye jambos ki list (Roman Urdu: Frontend se aane wale jambos) - convert to int
            new_jambos = set()
            for jambo in jambos:
                jambo_no = jambo.get('jambo_no')
                if jambo_no:
                    try:
                        new_jambos.add(int(jambo_no))
                    except (ValueError, TypeError):
                        print(f"⚠️  Skipping invalid jambo_no: {jambo_no}")
                        continue
            
            # Jo purane hain lekin naye nahi, unko delete karo (Roman Urdu: Delete missing jambos)
            jambos_to_delete = old_jambos - new_jambos
            print(f"🔍 Old jambos: {old_jambos}")
            print(f"🔍 New jambos: {new_jambos}")
            print(f"🔍 Jambos to delete: {jambos_to_delete}")
            
            for jambo_no in jambos_to_delete:
                cursor.execute("DELETE FROM jambo_rolls WHERE jambo_no = ? AND challan_no = ?", (jambo_no, original_challan))
                print(f"🗑️ Deleted jambo {jambo_no} from challan {original_challan}")
            
            cursor.execute('COMMIT')
            
            return jsonify({
                'success': True,
                'message': f'Successfully updated {updated_count} jambos',
                'saved_count': updated_count,
                'challan_no': new_challan,
                'party_name': party_name
            })
            
        except Exception as e:
            cursor.execute('ROLLBACK')
            print(f"❌ Error in transaction: {str(e)}")
            raise
        
        finally:
            conn.close()
        
    except Exception as e:
        print(f"Error updating challan: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error updating challan: {str(e)}'
                })

@bp.route('/api/challans/delete/<challan_no>', methods=['DELETE'])
def delete_challan(challan_no):
    """Delete entire challan and all its jambos, only if no production exists for any jambo"""
    try:
        print(f"🗑️ Delete challan API called for: {challan_no}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Begin transaction
        cursor.execute('BEGIN TRANSACTION')
        
        try:
            # First check if challan exists
            cursor.execute("SELECT COUNT(*) FROM jambo_rolls WHERE challan_no = ?", (challan_no,))
            challan_count = cursor.fetchone()[0]
            
            if challan_count == 0:
                cursor.execute('ROLLBACK')
                return jsonify({
                    'success': False,
                    'message': f'Challan {challan_no} nahi mila!'
                })
            
            print(f"🔍 Found {challan_count} jambos in challan {challan_no}")
            
            # Get all jambo numbers for this challan
            cursor.execute("SELECT jambo_no FROM jambo_rolls WHERE challan_no = ?", (challan_no,))
            jambo_numbers = [row[0] for row in cursor.fetchall()]
            
            # Check for production orders for each jambo
            jambos_with_production = []
            for jambo_no in jambo_numbers:
                cursor.execute("SELECT COUNT(*) FROM production_orders WHERE jambo_no = ?", (jambo_no,))
                production_count = cursor.fetchone()[0]
                if production_count > 0:
                    jambos_with_production.append(jambo_no)
            
            # If any jambos have production, do NOT delete and return error
            if jambos_with_production:
                cursor.execute('ROLLBACK')
                return jsonify({
                    'success': False,
                    'message': f'In jambos mein production hui hai, pehle production delete karein: {", ".join(str(j) for j in jambos_with_production)}'
                })
            
            # Now delete all jambos for this challan
            cursor.execute("DELETE FROM jambo_rolls WHERE challan_no = ?", (challan_no,))
            deleted_count = cursor.rowcount
            
            print(f"🗑️ Deleted {deleted_count} jambos from challan {challan_no}")
            
            # Commit transaction
            cursor.execute('COMMIT')
            
            return jsonify({
                'success': True,
                'message': f'Challan {challan_no} aur {deleted_count} jambos successfully delete ho gaye!',
                'deleted_count': deleted_count,
                'challan_no': challan_no
            })
            
        except Exception as e:
            cursor.execute('ROLLBACK')
            print(f"❌ Error in delete transaction: {str(e)}")
            raise
        
        finally:
            conn.close()
        
    except Exception as e:
        print(f"❌ Error deleting challan: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error deleting challan: {str(e)}'
        })

@bp.route('/jambos/pdf', methods=['GET', 'POST'])
def export_jambos_simple_pdf():
    """Roman Urdu: Simple PDF export - HTML based working version, ab POST se filtered data bhi accept karega"""
    try:
        jambos = None
        if request.method == 'POST':
            data = request.get_json()
            jambos = data.get('jambos', None)
        if not jambos:
            # Agar POST nahi hai ya data nahi mila, to pura database export karo
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT jambo_no, date, size_mm, size_meter, colour, micron, roll_no, 
                       net_weight, party_name, calculated_yard, balance_yard
                FROM jambo_rolls 
                ORDER BY jambo_no DESC
            """)
            jambos = cursor.fetchall()
            conn.close()
        else:
            # Agar frontend se data aaya hai, to usko tuple list bana lo
            jambos = [
                (
                    j['jambo_no'],
                    j['date'],
                    j['size'].split('×')[0].replace('mm','').strip() if 'size' in j else '',
                    j['size'].split('×')[1].replace('m','').strip() if 'size' in j and '×' in j['size'] else '',
                    j['colour'],
                    j['micron'],
                    j['roll_no'],
                    j['net_weight'].replace('kg','').strip(),
                    j['party_name'],
                    j['calculated_yard'],
                    j['balance_yard']
                ) for j in jambos
            ]

        timestamp = datetime.now().strftime('%d%m%Y_%H%M')
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Jambo Report {timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; margin-bottom: 25px; border-radius: 8px; }}
        .header h1 {{ font-size: 22px; font-weight: bold; margin: 0; }}
        .data-box {{ background: white; border: 3px solid #34495e; border-radius: 10px; padding: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        th {{ background: #34495e; color: white; padding: 12px 8px; text-align: center; font-weight: bold; border: 1px solid #2c3e50; }}
        td {{ padding: 10px 8px; text-align: center; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:nth-child(odd) {{ background: white; }}
        .jambo-no {{ font-weight: bold; color: #2c3e50; }}
        .colour-cell {{ font-weight: bold; color: #e74c3c; }}
        @media print {{ body {{ padding: 10px; background: white; }} .data-box {{ border: 2px solid #34495e; box-shadow: none; }} th, td {{ padding: 8px 6px; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 JAMBO ROLLS INVENTORY</h1>
    </div>
    <div class="data-box">
        <table>
            <thead>
                <tr>
                    <th>Jambo No</th>
                    <th>Date</th>
                    <th>Size</th>
                    <th>Colour</th>
                    <th>Micron</th>
                    <th>Roll No</th>
                    <th>Weight</th>
                    <th>Party</th>
                    <th>Calc Yard</th>
                    <th>Balance</th>
                </tr>
            </thead>
            <tbody>'''
        for jambo in jambos:
            formatted_date = ''
            try:
                # Pehle try karo YYYY-MM-DD ko DD-MM-YYYY banane ka
                formatted_date = datetime.strptime(jambo[1], '%Y-%m-%d').strftime('%d-%m-%Y') if jambo[1] else ''
            except:
                try:
                    # Agar already DD-MM-YYYY hai to waise hi rakh lo
                    formatted_date = datetime.strptime(jambo[1], '%d-%m-%Y').strftime('%d-%m-%Y') if jambo[1] else ''
                except:
                    formatted_date = jambo[1] or ''
            size_display = f"{jambo[2]}mm x {jambo[3]}m" if jambo[2] and jambo[3] else ''
            html_content += f'''
                <tr>
                    <td class="jambo-no">{jambo[0]}</td>
                    <td>{formatted_date}</td>
                    <td>{size_display}</td>
                    <td class="colour-cell">{jambo[4]}</td>
                    <td>{jambo[5]}</td>
                    <td>{jambo[6]}</td>
                    <td>{jambo[7]} kg</td>
                    <td>{jambo[8]}</td>
                    <td>{jambo[9]}</td>
                    <td>{jambo[10]}</td>
                </tr>'''
        html_content += '''
            </tbody>
        </table>
    </div>
</body>
</html>'''
        response = make_response(html_content)
        filename = f"JAMBO_REPORT_{timestamp}.html"
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    except Exception as e:
        print(f'Error generating PDF: {str(e)}')
        import traceback
        traceback.print_exc()
        return f"PDF export error: {str(e)}", 500 

@bp.route('/api/jambos/list')
def get_jambos_list():
    """Get list of all jambos with production data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all jambos with production data
        cursor.execute("""
            SELECT j.jambo_no, j.date, j.size_mm, j.size_meter, j.colour, j.micron,
                   j.roll_no, j.net_weight, j.party_name, j.calculated_yard,
                   COALESCE(SUM(po.yards_used), 0) as used_yards,
                   CASE WHEN c.jambo_id IS NOT NULL THEN 'CLOSED' ELSE 'ACTIVE' END as status,
                   j.calculated_yard - COALESCE(SUM(po.yards_used), 0) as balance_yard
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            LEFT JOIN production_orders po ON j.jambo_no = po.jambo_no
            GROUP BY j.jambo_no, j.date, j.size_mm, j.size_meter, j.colour, j.micron,
                     j.roll_no, j.net_weight, j.party_name, j.calculated_yard
            ORDER BY j.date DESC, j.jambo_no DESC
        """)
        
        jambos = cursor.fetchall()
        print(f"🔍 DEBUG: Found {len(jambos)} jambos")
        
        # Convert to list of dicts
        jambos_list = []
        for jambo in jambos:
            calculated_yard = jambo[9] if jambo[9] else 0
            used_yards = jambo[10] if jambo[10] else 0
            balance_yard = jambo[12] if jambo[12] else 0
            
            # Ensure balance is not negative
            if balance_yard < 0:
                balance_yard = 0
            
            print(f"🔍 DEBUG: Processing Jambo #{jambo[0]}:")
            print(f"- Calculated: {calculated_yard}")
            print(f"- Used: {used_yards}")
            print(f"- Balance: {balance_yard}")
            
            jambos_list.append({
                'jambo_no': jambo[0],
                'date': jambo[1],
                'size_mm': jambo[2],
                'size_meter': jambo[3],
                'colour': jambo[4],
                'micron': jambo[5],
                'roll_no': jambo[6],
                'net_weight': jambo[7],
                'party_name': jambo[8],
                'calculated_yard': calculated_yard,
                'used_yards': used_yards,
                'balance_yard': balance_yard,
                'status': jambo[11]
            })
        
        conn.close()
        return jsonify({
            'success': True,
            'jambos': jambos_list
        })
        
    except Exception as e:
        print(f"❌ ERROR in get_jambos_list: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        }) 