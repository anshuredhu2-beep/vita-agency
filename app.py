from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os

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
    stock = db.Column(db.Integer, nullable=False, default=0)

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

# Routes
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
        counters = Counter.query.all()
        return render_template('driver_dashboard.html', products=products, counters=counters)
    return redirect(url_for('login'))

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user' in session and session.get('role') == 'admin':
        name = request.form['name']
        p_rate = float(request.form['purchase_rate'])
        s_rate = float(request.form['selling_rate'])
        stock = int(request.form['stock'])
        
        prod = Product(name=name, purchase_rate=p_rate, selling_rate=s_rate, stock=stock)
        db.session.add(prod)
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
        total = qty * prod.selling_rate if prod else 0
        
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
