# 🎬 Jambo Management Cloud System

Desktop version se convert kiya gaya complete web-based plastic film manufacturing aur inventory management system.

## 🚀 Features

### 📦 Jambo Rolls Management
- Add, edit, delete jambo rolls
- Real-time search functionality
- Auto-calculation of yards (meter to yard conversion)
- Balance tracking aur usage percentage
- Party-wise inventory

### 📄 Customer Orders Management
- Complete order management system
- Order items with detailed specifications
- Real-time order tracking
- Customer details aur contact management

### 🏭 Production Management
- Smart production system
- Jambo-to-order matching
- Production calculation aur feasibility check
- Automatic yard deduction
- Production history tracking

### 📊 Dashboard & Reports
- Real-time statistics
- Recent activities tracking
- Inventory overview
- Production analytics

## 💻 Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: Bootstrap 5, jQuery
- **Icons**: Font Awesome
- **Responsive**: Mobile-friendly design

## 🛠️ Installation

### 1. Requirements
```bash
# Python 3.7+ required
python --version
```

### 2. Setup Virtual Environment
```bash
# Create virtual environment
python -m venv jambo_env

# Activate (Windows)
jambo_env\Scripts\activate

# Activate (Linux/Mac)
source jambo_env/bin/activate
```

### 3. Install Dependencies
```bash
cd cloud
pip install -r requirements.txt
```

### 4. Run Application
```bash
python app.py
```

### 5. Access Application
Open browser aur jaiye: **http://localhost:5000**

## 📁 Project Structure

```
cloud/
├── app.py              # Main Flask application
├── models.py           # Database models
├── requirements.txt    # Dependencies
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── dashboard.html  # Dashboard page
│   ├── jambos.html     # Jambo listing
│   ├── add_jambo.html  # Add jambo form
│   └── orders.html     # Orders listing
├── static/             # Static files
│   ├── css/
│   │   └── style.css   # Custom styles
│   └── js/
│       └── main.js     # JavaScript functions
└── jambo_cloud.db     # SQLite database (auto-created)
```

## 🎯 Usage Guide

### Dashboard
- System ka overview dekhne ke liye
- Quick actions aur stats
- Recent activities

### Jambo Management
1. **Add Jambo**: New jambo roll add karo
2. **Search**: Real-time search by jambo#, color, party
3. **Edit**: Existing jambos update karo
4. **Delete**: Unwanted jambos remove karo

### Order Management
1. **New Order**: Customer order create karo
2. **Add Items**: Order mein items add karo
3. **Track Status**: Order status monitor karo
4. **Edit**: Order details update karo

### Production
1. **Smart Production**: Automatic jambo-order matching
2. **Calculate**: Production requirements calculate karo
3. **Execute**: Production start karo
4. **Track**: Production progress monitor karo

## 🔧 Configuration

### Database
- SQLite database automatically create hoti hai
- Sample data insert hota hai first run mein
- Database file: `jambo_cloud.db`

### Default Settings
```python
# Jambo width: 1280mm
# Meter to yard ratio: 1.08325
# Default rate: ₨750 per kg
# Default micron: 37mic
```

## 🌐 API Endpoints

### Jambo APIs
- `GET /jambos` - List all jambos
- `POST /jambos/add` - Add new jambo
- `POST /jambos/edit/<id>` - Edit jambo
- `POST /jambos/delete/<id>` - Delete jambo

### Order APIs
- `GET /orders` - List all orders
- `POST /orders/add` - Add new order
- `POST /orders/<id>/add_item` - Add item to order

### Production APIs
- `GET /production` - List productions
- `POST /api/production/calculate` - Calculate production requirements

## 📱 Mobile Support

- Fully responsive design
- Touch-friendly interface
- Mobile-optimized forms
- Bootstrap 5 responsive grid

## 🔍 Search Features

- **Real-time search**: Type aur instantly results
- **Multi-field search**: Jambo#, color, party, micron
- **Debounced input**: Performance optimized
- **Clear filters**: Easy reset functionality

## 🎨 UI Features

- **Modern design**: Clean aur professional
- **Color coding**: Status-based visual indicators
- **Progress bars**: Usage percentage tracking
- **Hover effects**: Interactive elements
- **Loading states**: User feedback
- **Toast notifications**: Success/error messages

## 🔒 Security

- Input validation aur sanitization
- SQL injection prevention (SQLAlchemy)
- XSS protection
- Form CSRF protection (can be added)

## 📈 Performance

- Optimized database queries
- Efficient search algorithms
- Lazy loading for large datasets
- Caching for static resources

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Change port in app.py
   app.run(port=5001)
   ```

2. **Database errors**
   ```bash
   # Delete database file and restart
   rm jambo_cloud.db
   python app.py
   ```

3. **Module not found**
   ```bash
   # Install dependencies again
   pip install -r requirements.txt
   ```

## 🔄 Updates

### From Desktop Version
- Same database schema maintained
- All features ported to web
- Enhanced UI/UX
- Mobile support added
- Real-time features
- Modern web technologies

## 🤝 Support

Agar koi problem hai ya suggestion hai:
1. Check troubleshooting section
2. Review error logs
3. Contact development team

## 📝 License

Internal use only - Jambo Management System

## 🎉 Credits

Developed with ❤️ using Flask
Desktop to Web conversion completed
Roman Urdu comments for easy understanding

---

**🌟 Happy Manufacturing! 🌟** 