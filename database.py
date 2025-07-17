"""
Database initialization and connection management
"""
import sqlite3
import os
from config import Config

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def fix_parties_table():
    """Fix parties table schema"""
    print("🔧 Fixing parties table schema...")
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    
    try:
        # Backup existing data with party types
        cursor.execute("SELECT id, name, party_type, phone, email, address, city, created_date, is_active FROM parties")
        existing_data = cursor.fetchall()
        
        # Drop existing table
        cursor.execute("DROP TABLE IF EXISTS parties")
        
        # Recreate table with correct schema
        cursor.execute('''
            CREATE TABLE parties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                party_type TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                city TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Restore data with original party types
        if existing_data:
            for row in existing_data:
                cursor.execute('''
                    INSERT INTO parties (name, party_type, phone, email, address, city, created_date, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
        
        conn.commit()
        print("✅ Parties table fixed successfully")
        
    except Exception as e:
        print(f"❌ Error fixing parties table: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def add_sample_data():
    """Add sample data to database for testing"""
    print("🔧 Adding sample data...")
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    
    try:
        # Add sample order
        cursor.execute('''
            INSERT OR IGNORE INTO customer_orders 
            (order_no, order_date, customer_name, customer_phone, status)
            VALUES ('OR-0001', '2024-12-29', 'Kami', '03001234567', 'Pending')
        ''')
        
        # Add sample items
        sample_items = [
            ('OR-0001', '69mm x 72 Yard', '480 Pcs', 37, 'Clear', 'Clear', 'Standard', '48', '', 0, 0, ''),
            ('OR-0001', '46mm x 72 Yard', '864 Pcs', 37, 'Clear', 'Clear', 'Standard', '48', '', 0, 0, '')
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO order_items 
            (order_no, size, qty, micron, brand, colour, variety, packing, printed_matter, unit_price, amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_items)
        
        # Add sample jambo
        cursor.execute('''
            INSERT OR IGNORE INTO jambo_rolls (
                jambo_no, date, size_mm, size_meter, colour, micron, roll_no,
                net_weight, party_name, calculated_yard, actual_yard, rate_kg,
                amount, balance_yard, extra_yard
            ) VALUES (
                1013, '2024-12-29', 1280, 72, 'Clear', 37, 1,
                450.5, 'Test Party', 7800, 7800, 850,
                382925, 7800, 0
            )
        ''')
        
        conn.commit()
        print("✅ Sample data added successfully")
        
    except Exception as e:
        print(f"❌ Error adding sample data: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def init_database(add_samples=False):
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create jambo_rolls table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jambo_rolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jambo_no INTEGER UNIQUE NOT NULL,
            date TEXT NOT NULL,
            size_mm INTEGER NOT NULL,
            size_meter REAL NOT NULL,
            colour TEXT NOT NULL,
            micron INTEGER NOT NULL,
            roll_no INTEGER NOT NULL,
            net_weight REAL NOT NULL,
            party_name TEXT NOT NULL,
            calculated_yard INTEGER NOT NULL,
            actual_yard INTEGER NOT NULL,
            rate_kg REAL NOT NULL,
            amount REAL NOT NULL,
            balance_yard INTEGER NOT NULL,
            extra_yard INTEGER DEFAULT 0,
            challan_no TEXT
        )
    ''')
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            order_date TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT,
            customer_address TEXT,
            status TEXT DEFAULT 'Pending',
            total_amount REAL DEFAULT 0
        )
    ''')
    
    # Create order_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL,
            size TEXT NOT NULL,
            size_mm INTEGER,
            size_yard INTEGER,
            qty TEXT NOT NULL,
            micron INTEGER NOT NULL,
            brand TEXT NOT NULL,
            colour TEXT NOT NULL,
            variety TEXT NOT NULL,
            packing TEXT NOT NULL,
            printed_matter TEXT,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (order_no) REFERENCES customer_orders (order_no)
        )
    ''')
    
    # Add size_mm and size_yard columns if they don't exist
    try:
        cursor.execute('ALTER TABLE order_items ADD COLUMN size_mm INTEGER')
    except:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE order_items ADD COLUMN size_yard INTEGER')
    except:
        pass  # Column already exists
    
    # Create parties table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            party_type TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            city TEXT,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Create production_orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL,
            jambo_no INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            produced_pieces INTEGER DEFAULT 0,
            production_date TEXT NOT NULL,
            shafts_used INTEGER DEFAULT 0,
            yards_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'In Progress',
            FOREIGN KEY (jambo_no) REFERENCES jambo_rolls (jambo_no)
        )
    ''')
    
    # Create closed_jambos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closed_jambos (
            jambo_id INTEGER PRIMARY KEY,
            closed_date TEXT NOT NULL,
            FOREIGN KEY (jambo_id) REFERENCES jambo_rolls (jambo_no)
        )
    ''')
    
    # Create closed_order_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closed_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            closed_date TEXT NOT NULL,
            closed_reason TEXT DEFAULT 'Manual Close',
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(order_no, item_id),
            FOREIGN KEY (order_no) REFERENCES customer_orders (order_no),
            FOREIGN KEY (item_id) REFERENCES order_items (item_id)
        )
    ''')
    
    # Create challan_sequence table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS challan_sequence (
            id INTEGER PRIMARY KEY,
            last_challan_no INTEGER DEFAULT 0
        )
    ''')
    
    # Create stock_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            size_mm INTEGER NOT NULL,
            size_yard INTEGER NOT NULL,
            color TEXT NOT NULL,
            brand TEXT NOT NULL,
            micron INTEGER NOT NULL,
            packing INTEGER DEFAULT 72,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            UNIQUE(size_mm, size_yard, color, brand, micron)
        )
    ''')
    
    # Add packing column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE stock_items ADD COLUMN packing INTEGER DEFAULT 72')
    except:
        pass  # Column already exists
    
    # Create stock_transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            transaction_date TEXT NOT NULL,
            transaction_type TEXT NOT NULL,  -- 'production' or 'sale'
            quantity INTEGER NOT NULL,
            reference_id TEXT NOT NULL,      -- production_id or order_id
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES stock_items (id)
        )
    ''')
    
    # Add bill_counter table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bill_counter (
        id INTEGER PRIMARY KEY,
        last_number INTEGER DEFAULT 0
    )''')
    
    # Reset bill counter to 0
    cursor.execute('DELETE FROM bill_counter')
    cursor.execute('INSERT INTO bill_counter (id, last_number) VALUES (1, 0)')
    
    # Create bills table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            bill_no TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create bill_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no TEXT NOT NULL,
            qty TEXT NOT NULL,
            size TEXT NOT NULL,
            colour TEXT NOT NULL,
            brand TEXT NOT NULL,
            mic TEXT NOT NULL,
            printed TEXT,
            varity TEXT,
            per_ctn_qty TEXT,
            rate REAL DEFAULT 0,
            FOREIGN KEY (bill_no) REFERENCES bills (bill_no)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Fix parties table if needed
    fix_parties_table()
    
    # Add sample data if requested
    if add_samples:
        add_sample_data()
    
    print("✅ Database initialized successfully") 

def get_next_bill_number():
    """Get next bill number in FC-XXXX format"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First check if counter exists, if not initialize it
    cursor.execute('SELECT COUNT(*) FROM bill_counter')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO bill_counter (id, last_number) VALUES (1, 0)')
        conn.commit()
    
    cursor.execute('UPDATE bill_counter SET last_number = last_number + 1 WHERE id = 1 RETURNING last_number')
    number = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    return f'FC-{number:04d}'  # Format: FC-0001, FC-0002, etc. 