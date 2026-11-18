from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'shivshankar_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vita_agency.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'driver'
    route_name = db.Column(db.String(80), nullable=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    purchase_rate = db.Column(db.Float, nullable=False, default=0.0)
    selling_rate = db.Column(db.Float, nullable=False, default=0.0)
    shop_stock = db.Column(db.Integer, nullable=False, default=0)

class DriverStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    item_name = db.Column(db.String(80), nullable=False)
    vehicle_stock = db.Column(db.Integer, nullable=False, default=0)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    counter_name = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(20), nullable=False)

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
            return redirect(url_for('admin_dashboard') if user.role == 'admin' else url_for('driver_dashboard'))
        else:
            return "Invalid Username or Password", 401
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'user' in session and session.get('role') == 'admin':
        products = Product.query.all()
        drivers = User.query.filter_by(role='driver').all()
        driver_stocks = DriverStock.query.all()
        sales = Sale.query.all()
        
        # Calculate summary per driver for Admin
        driver_summaries = []
        for d in drivers:
            d_sales = [s for s in sales if s.driver_username == d.username]
            d_cash = sum(s.total_amount for s in d_sales if s.payment_mode == 'Cash')
            d_upi = sum(s.total_amount for s in d_sales if s.payment_mode == 'UPI')
            d_udhar = sum(s.total_amount for s in d_sales if s.payment_mode == 'Udhar')
            driver_summaries.append({
                'username': d.username,
                'route_name': d.route_name,
                'cash': d_cash,
                'upi': d_upi,
                'udhar': d_udhar,
                'sales': d_sales
            })
            
        return render_template('admin_dashboard.html', products=products, drivers=drivers, 
                             driver_stocks=driver_stocks, driver_summaries=driver_summaries)
    return redirect(url_for('login'))

@app.route('/driver')
def driver_dashboard():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        driver_stocks = DriverStock.query.filter_by(driver_username=driver_name).all()
        sales = Sale.query.filter_by(driver_username=driver_name).all()
        
        total_cash = sum(s.total_amount for s in sales if s.payment_mode == 'Cash')
        total_upi = sum(s.total_amount for s in sales if s.payment_mode == 'UPI')
        total_udhar = sum(s.total_amount for s in sales if s.payment_mode == 'Udhar')
        
        return render_template('driver_dashboard.html', driver_stocks=driver_stocks, sales=sales,
                             total_cash=total_cash, total_upi=total_upi, total_udhar=total_udhar)
    return redirect(url_for('login'))

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

@app.route('/load_vehicle', methods=['POST'])
def load_vehicle():
    if 'user' in session and session.get('role') == 'admin':
        driver_name = request.form['driver_username']
        item_name = request.form['item_name']
        load_qty = int(request.form['load_qty'])
        
        prod = Product.query.filter_by(name=item_name).first()
        if prod and prod.shop_stock >= load_qty:
            prod.shop_stock -= load_qty
            
            d_stock = DriverStock.query.filter_by(driver_username=driver_name, item_name=item_name).first()
            if d_stock:
                d_stock.vehicle_stock += load_qty
            else:
                d_stock = DriverStock(driver_username=driver_name, item_name=item_name, vehicle_stock=load_qty)
                db.session.add(d_stock)
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
        driver_name = session['user']
        counter = request.form['counter_name']
        item = request.form['item_name']
        qty = int(request.form['quantity'])
        mode = request.form['payment_mode']
        
        d_stock = DriverStock.query.filter_by(driver_username=driver_name, item_name=item).first()
        prod = Product.query.filter_by(name=item).first()
        
        if d_stock and prod and d_stock.vehicle_stock >= qty:
            d_stock.vehicle_stock -= qty
            total = qty * prod.selling_rate
            
            sale = Sale(driver_username=driver_name, counter_name=counter, item_name=item, quantity=qty, total_amount=total, payment_mode=mode)
            db.session.add(sale)
            db.session.commit()
            
        return redirect(url_for('driver_dashboard'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', role='admin')
        db.session.add(admin_user)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
