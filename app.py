"""
Main Flask Application for Jambo Management System
Modular version with separate blueprints
"""
import os
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from config import Config
from database import init_database, get_db_connection
from routes import register_blueprints

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'al-wasiqa-secret-key-2025'  # Session ke liye secret key

# Template filters
@app.template_filter('safe_float')
def safe_float(value):
    """Safely convert value to float for formatting"""
    try:
        if value is None or value == '':
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0

@app.template_filter('format_date')
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

# Register all blueprints
register_blueprints(app)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with authentication"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Simple authentication - aap ise database se connect kar sakte hain
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Dashboard with basic statistics"""
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get active jambos count (excluding closed ones)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
        """)
        total_jambos = cursor.fetchone()[0] or 0
        
        # Get active orders count (excluding completed/cancelled)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM customer_orders 
            WHERE status IN ('Pending', 'In Progress', 'Partial')
        """)
        total_orders = cursor.fetchone()[0] or 0
        
        # Get active parties count
        cursor.execute("SELECT COUNT(*) FROM parties WHERE is_active = 1")
        total_parties = cursor.fetchone()[0] or 0
        
        # Get recent active jambos
        cursor.execute('''
            SELECT j.jambo_no, j.date, j.colour, j.party_name, j.balance_yard,
                   CASE WHEN c.jambo_id IS NOT NULL THEN 'CLOSED' ELSE 'ACTIVE' END as status
            FROM jambo_rolls j
            LEFT JOIN closed_jambos c ON j.jambo_no = c.jambo_id
            WHERE c.jambo_id IS NULL
            ORDER BY j.date DESC, j.jambo_no DESC 
            LIMIT 5
        ''')
        recent_jambos = cursor.fetchall()
        
        # Get recent active orders with items count and amount
        cursor.execute('''
            SELECT o.order_no, o.order_date, o.customer_name, o.status,
                   COUNT(i.item_id) as items_count,
                   COALESCE(SUM(i.amount), 0) as total_amount
            FROM customer_orders o
            LEFT JOIN order_items i ON o.order_no = i.order_no
            WHERE o.status IN ('Pending', 'In Progress', 'Partial')
            GROUP BY o.order_no, o.order_date, o.customer_name, o.status
            ORDER BY o.order_date DESC 
            LIMIT 5
        ''')
        recent_orders = cursor.fetchall()
        
        # Get pending orders count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM customer_orders 
            WHERE status = 'Pending'
        """)
        pending_orders = cursor.fetchone()[0] or 0
        
        # Get production orders count
        cursor.execute("""
            SELECT COUNT(DISTINCT po.order_no) 
            FROM production_orders po
            INNER JOIN customer_orders co ON po.order_no = co.order_no
            WHERE co.status IN ('In Progress', 'Partial')
        """)
        production_orders = cursor.fetchone()[0] or 0
        
        # Convert jambos to list of dicts
        jambos_list = []
        for jambo in recent_jambos:
            jambos_list.append({
                'jambo_no': jambo[0],
                'date': format_date(jambo[1]) if jambo[1] else '',
                'colour': jambo[2],
                'party_name': jambo[3],
                'balance_yard': jambo[4] or 0,
                'status': jambo[5]
            })
        
        # Convert orders to list of dicts
        orders_list = []
        for order in recent_orders:
            orders_list.append({
                'order_no': order[0],
                'order_date': format_date(order[1]) if order[1] else '',
                'customer_name': order[2],
                'status': order[3],
                'items_count': order[4] or 0,
                'total_amount': float(order[5] or 0)
            })
        
        # Close database connection
        conn.close()
        
        return render_template('simple_dashboard.html',
                             total_jambos=total_jambos,
                             total_orders=total_orders,
                             total_parties=total_parties,
                             recent_jambos=jambos_list,
                             recent_orders=orders_list,
                             pending_orders=pending_orders,
                             production_orders=production_orders)
                             
    except Exception as e:
        print(f"Dashboard error: {e}")
        if 'conn' in locals():
            conn.close()
        return render_template('simple_dashboard.html',
                             total_jambos=0,
                             total_orders=0,
                             total_parties=0,
                             recent_jambos=[],
                             recent_orders=[],
                             pending_orders=0,
                             production_orders=0)

if __name__ == '__main__':
    print("🗄️ Initializing database...")
    try:
        init_database(add_samples=False)  # Initialize without sample data
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    print("🌐 Starting Flask server...")
    print("📍 Server URL: http://localhost:5000")
    print("📍 Network URL: http://0.0.0.0:5000")
    
    try:
        app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"❌ Server start error: {e}")
        traceback.print_exc() 