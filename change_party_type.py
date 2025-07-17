"""
Change party type in database
"""
from database import get_db_connection

def show_parties():
    """Show all parties"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, party_type, is_active
        FROM parties
        ORDER BY name
    """)
    
    parties = cursor.fetchall()
    
    print("\n📋 Current Parties:")
    print("-" * 50)
    for i, party in enumerate(parties, 1):
        name = party[0]
        party_type = party[1] if party[1] else 'NO TYPE'
        is_active = "✅ Active" if party[2] else "❌ Inactive"
        print(f"{i}. {name:30} Type: {party_type:15} Status: {is_active}")
    
    conn.close()
    return parties

def change_party_type():
    """Change party type"""
    try:
        parties = show_parties()
        
        if not parties:
            print("\n❌ No parties found in database!")
            return
        
        print("\n🔄 Change Party Type")
        print("-" * 50)
        print("Enter the number of the party to change (or 'q' to quit)")
        choice = input("Choice: ").strip()
        
        if choice.lower() == 'q':
            return
            
        try:
            party_index = int(choice) - 1
            if party_index < 0 or party_index >= len(parties):
                print("❌ Invalid party number!")
                return
        except ValueError:
            print("❌ Please enter a valid number!")
            return
            
        selected_party = parties[party_index]
        
        print(f"\n✨ Selected Party: {selected_party[0]}")
        print(f"Current Type: {selected_party[1] if selected_party[1] else 'NO TYPE'}")
        print("\nAvailable Types:")
        print("1. supplier")
        print("2. customer")
        print("3. other")
        print("\nEnter the number of new type (or 'q' to quit)")
        
        type_choice = input("New Type: ").strip()
        
        if type_choice.lower() == 'q':
            return
            
        type_map = {
            '1': 'supplier',
            '2': 'customer',
            '3': 'other'
        }
        
        if type_choice not in type_map:
            print("❌ Invalid type choice!")
            return
            
        new_type = type_map[type_choice]
        
        # Update database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE parties
            SET party_type = ?
            WHERE name = ?
        """, (new_type, selected_party[0]))
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Successfully changed {selected_party[0]} to type: {new_type}")
        
        # Show updated list
        print("\n📋 Updated Party List:")
        show_parties()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    while True:
        change_party_type()
        print("\n🔄 Do you want to change another party? (y/n)")
        if input().lower() != 'y':
            break
    print("\n👋 Goodbye!") 