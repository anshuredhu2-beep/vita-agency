from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'shivshankar_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vita_agency.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 1. User Model (Admin & Drivers)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'driver'
    route_name = db.Column(db.String(80), nullable=True)

# 2. Product Model (Milk, Dahi, Paneer, Ghee, Bread, etc.)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    purchase_rate = db.Column(db.Float, nullable=False, default=0.0)
    selling_rate = db.Column(db.Float, nullable=False, default=0.0)
    shop_stock = db.Column(db.Integer, nullable=False, default=0)      # Dukaan par rakha maal
    vehicle_stock = db.Column(db.Integer, nullable=False, default=0)   # Gaadi mein load hua maal

# 3. Counter / Shop Model
class Counter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    route_name = db.Column(db.String(80), nullable=False)

# 4. Sale / Transaction Model
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    counter_name = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(20), nullable=False)  # Cash, UPI, Udhar

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('driver_dashboard'))
        else:
            return "Invalid Username or Password", 401
            
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'user' in session and session.get('role') == 'admin':
        products = Product.query.all()
        drivers = User.query.filter_by(role='driver').all()
        sales = Sale.query.all()
        return render_template('admin_dashboard.html', products=products, drivers=drivers, sales=sales)
    return redirect(url_for('login'))

@app.route('/driver')
def driver_dashboard():
    if 'user' in session and session.get('role') == 'driver':
        products = Product.query.all()
        return render_template('driver_dashboard.html', products=products)
    return redirect(url_for('login'))

# Add or Update Product & Rates
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user' in session and session.get('role') == 'admin':
        name = request.form['name']
        p_rate = float(request.form['purchase_rate'])
        s_rate = float(request.form['selling_rate'])
        shop_stock = int(request.form['shop_stock'])
        
        prod = Product.query.filter_by(name=name).first()
        if prod:
            prod.purchase_rate = p_rate
            prod.selling_rate = s_rate
            prod.shop_stock += shop_stock
        else:
            prod = Product(name=name, purchase_rate=p_rate, selling_rate=s_rate, shop_stock=shop_stock)
            db.session.add(prod)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

# Load Stock into Driver Vehicle for Route
@app.route('/load_vehicle', methods=['POST'])
def load_vehicle():
    if 'user' in session and session.get('role') == 'admin':
        item_name = request.form['item_name']
        load_qty = int(request.form['load_qty'])
        
        prod = Product.query.filter_by(name=item_name).first()
        if prod and prod.shop_stock >= load_qty:
            prod.shop_stock -= load_qty       # Dukaan ke stock se ghata
            prod.vehicle_stock += load_qty    # Gaadi ke stock mein joda
            db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/add_driver', methods=['POST'])
def add_driver():
    if 'user' in session and session.get('role') == 'admin':
        username = request.form['username']
        password = request.form['password']
        route = request.form['route_name']
        
        drv = User(username=username, password=password, role='driver', route_name=route)
        db.session.add(drv)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/record_sale', methods=['POST'])
def record_sale():
    if 'user' in session and session.get('role') == 'driver':
        counter = request.form['counter_name']
        item = request.form['item_name']
        qty = int(request.form['quantity'])
        mode = request.form['payment_mode']
        
        prod = Product.query.filter_by(name=item).first()
        if prod and prod.vehicle_stock >= qty:
            prod.vehicle_stock -= qty  # Gaadi ke stock se bik gaya
            total = qty * prod.selling_rate
            
            sale = Sale(driver_username=session['user'], counter_name=counter, item_name=item, quantity=qty, total_amount=total, payment_mode=mode)
            db.session.add(sale)
            db.session.commit()
            
        return redirect(url_for('driver_dashboard'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Initialize Database & Default Admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', role='admin')
        db.session.add(admin_user)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
