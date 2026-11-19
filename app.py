from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'shivshankar_secret_key'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vita_agency.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)
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
    sale_date = db.Column(db.String(20), nullable=False)


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            session['role'] = user.role
            return redirect(url_for('admin_dashboard') if user.role == 'admin' else url_for('driver_dashboard'))
        flash("Galat Username ya Password!", "error")
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/admin')
def admin_dashboard():
    if 'user' in session and session.get('role') == 'admin':
        products = Product.query.order_by(Product.name.asc()).all()
        product_map = {p.name: p for p in products}
        drivers = User.query.filter_by(role='driver').order_by(User.username.asc()).all()
        driver_stocks = DriverStock.query.all()

        today_str = datetime.now().strftime('%Y-%m-%d')
        selected_date = request.args.get('sale_date', today_str)
        sales = Sale.query.filter_by(sale_date=selected_date).all()

        all_dates = db.session.query(Sale.sale_date).distinct().all()
        dates_list = [d[0] for d in all_dates]
        if today_str not in dates_list:
            dates_list.append(today_str)
        dates_list.sort(reverse=True)

        total_cash = round(sum(s.total_amount for s in sales if s.payment_mode == 'Cash'), 2)
        total_upi = round(sum(s.total_amount for s in sales if s.payment_mode == 'UPI'), 2)
        total_udhar = round(sum(s.total_amount for s in sales if s.payment_mode == 'Udhar'), 2)
        total_revenue = round(sum(s.total_amount for s in sales), 2)

        est_profit = 0.0
        for s in sales:
            p = product_map.get(s.item_name)
            p_rate = p.purchase_rate if p else 0.0
            est_profit += (s.total_amount - (s.quantity * p_rate))
        est_profit = round(est_profit, 2)

        item_summaries = []
        for p in products:
            item_sales = [s for s in sales if s.item_name == p.name]
            total_sold_qty = sum(s.quantity for s in item_sales)
            item_rev = round(sum(s.total_amount for s in item_sales), 2)
            total_vehicle_qty = sum(ds.vehicle_stock for ds in driver_stocks if ds.item_name == p.name)

            item_summaries.append({
                'name': p.name,
                'purchase_rate': p.purchase_rate,
                'selling_rate': p.selling_rate,
                'godown_stock': p.shop_stock,
                'vehicle_stock': total_vehicle_qty,
                'sold_qty': total_sold_qty,
                'revenue': item_rev
            })

        driver_summaries = []
        for d in drivers:
            d_sales = [s for s in sales if s.driver_username == d.username]
            d_stock = [ds for ds in driver_stocks if ds.driver_username == d.username and ds.vehicle_stock > 0]
            d_cash = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'Cash'), 2)
            d_upi = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'UPI'), 2)
            d_udhar = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'Udhar'), 2)

            driver_summaries.append({
                'username': d.username,
                'route_name': d.route_name,
                'cash': d_cash,
                'upi': d_upi,
                'udhar': d_udhar,
                'sales': d_sales,
                'stock': d_stock
            })

        return render_template(
            'admin_dashboard.html',
            products=products,
            drivers=drivers,
            item_summaries=item_summaries,
            driver_summaries=driver_summaries,
            selected_date=selected_date,
            dates_list=dates_list,
            total_cash=total_cash,
            total_upi=total_upi,
            total_udhar=total_udhar,
            total_revenue=total_revenue,
            est_profit=est_profit
        )
    return redirect(url_for('login'))


@app.route('/driver')
def driver_dashboard():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        driver_stocks = DriverStock.query.filter_by(driver_username=driver_name).all()

        today_str = datetime.now().strftime('%Y-%m-%d')
        sales = Sale.query.filter_by(driver_username=driver_name, sale_date=today_str).all()

        saved_counters_rows = db.session.query(Sale.counter_name).filter_by(driver_username=driver_name).distinct().all()
        saved_counters = sorted({c[0].strip() for c in saved_counters_rows if c[0] and c[0].strip()})

        total_cash = round(sum(s.total_amount for s in sales if s.payment_mode == 'Cash'), 2)
        total_upi = round(sum(s.total_amount for s in sales if s.payment_mode == 'UPI'), 2)
        total_udhar = round(sum(s.total_amount for s in sales if s.payment_mode == 'Udhar'), 2)

        return render_template(
            'driver_dashboard.html',
            driver_stocks=driver_stocks,
            sales=sales,
            saved_counters=saved_counters,
            today_date=today_str,
            total_cash=total_cash,
            total_upi=total_upi,
            total_udhar=total_udhar
        )
    return redirect(url_for('login'))


@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user' in session and session.get('role') == 'admin':
        selected_item = request.form.get('saved_item', '').strip()
        new_item = request.form.get('name', '').strip()
        name = new_item if (selected_item == '__NEW__' or new_item) else selected_item
        shop_stock = int(request.form.get('shop_stock') or 0)

        if name:
            prod = Product.query.filter(db.func.lower(Product.name) == name.lower()).first()
            p_rate_raw = request.form.get('purchase_rate', '').strip()
            s_rate_raw = request.form.get('selling_rate', '').strip()

            if prod:
                if p_rate_raw:
                    prod.purchase_rate = float(p_rate_raw)
                if s_rate_raw:
                    prod.selling_rate = float(s_rate_raw)
                prod.shop_stock += shop_stock
                flash(f"{prod.name} ka stock +{shop_stock} add ho gaya (Godown: {prod.shop_stock}).", "success")
            else:
                p_rate = float(p_rate_raw) if p_rate_raw else 0.0
                s_rate = float(s_rate_raw) if s_rate_raw else 0.0
                prod = Product(name=name, purchase_rate=p_rate, selling_rate=s_rate, shop_stock=shop_stock)
                db.session.add(prod)
                flash(f"Naya item '{name}' save ho gaya.", "success")

            db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/load_vehicle', methods=['POST'])
def load_vehicle():
    if 'user' in session and session.get('role') == 'admin':
        driver_name = request.form['driver_username']
        item_name = request.form['item_name']
        load_qty = int(request.form.get('load_qty') or 0)

        prod = Product.query.filter_by(name=item_name).first()
        if prod and load_qty > 0 and prod.shop_stock >= load_qty:
            prod.shop_stock -= load_qty

            d_stock = DriverStock.query.filter_by(driver_username=driver_name, item_name=item_name).first()
            if d_stock:
                d_stock.vehicle_stock += load_qty
            else:
                d_stock = DriverStock(driver_username=driver_name, item_name=item_name, vehicle_stock=load_qty)
                db.session.add(d_stock)
            db.session.commit()
            flash(f"{load_qty} {item_name} driver '{driver_name}' ki gaadi mein load ho gaya.", "success")
        else:
            flash("Godown mein itna stock maujood nahi hai ya quantity galat hai.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/receive_return', methods=['POST'])
def receive_return():
    if 'user' in session and session.get('role') == 'admin':
        driver_name = request.form['driver_username']
        item_name = request.form['item_name']
        return_qty = int(request.form.get('return_qty') or 0)

        d_stock = DriverStock.query.filter_by(driver_username=driver_name, item_name=item_name).first()
        prod = Product.query.filter_by(name=item_name).first()

        if d_stock and prod and return_qty > 0 and d_stock.vehicle_stock >= return_qty:
            d_stock.vehicle_stock -= return_qty
            prod.shop_stock += return_qty
            db.session.commit()
            flash(f"{return_qty} {item_name} wapsi godown mein jama ho gaya.", "success")
        else:
            flash("Gaadi mein itna return stock nahi hai ya quantity galat hai.", "error")

        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/add_driver', methods=['POST'])
def add_driver():
    if 'user' in session and session.get('role') == 'admin':
        username = request.form['username'].strip()
        password = request.form['password']
        route = request.form['route_name'].strip()

        if username and password and not User.query.filter_by(username=username).first():
            drv = User(username=username, password=password, role='driver', route_name=route)
            db.session.add(drv)
            db.session.commit()
            flash(f"Driver '{username}' ({route}) ban gaya.", "success")
        else:
            flash("Driver username pehle se maujood hai ya details adhoori hain.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/record_sale', methods=['POST'])
def record_sale():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        selected_counter = request.form.get('saved_counter', '').strip()
        new_counter = request.form.get('counter_name', '').strip()
        counter = new_counter if (selected_counter == '__NEW__' or new_counter) else selected_counter

        item = request.form.get('item_name', '').strip()
        qty = int(request.form.get('quantity') or 0)
        mode = request.form['payment_mode']
        today_str = datetime.now().strftime('%Y-%m-%d')

        d_stock = DriverStock.query.filter_by(driver_username=driver_name, item_name=item).first()
        prod = Product.query.filter_by(name=item).first()

        if counter and d_stock and prod and qty > 0 and d_stock.vehicle_stock >= qty:
            d_stock.vehicle_stock -= qty
            total = round(qty * prod.selling_rate, 2)

            sale = Sale(
                driver_username=driver_name,
                counter_name=counter,
                item_name=item,
                quantity=qty,
                total_amount=total,
                payment_mode=mode,
                sale_date=today_str
            )
            db.session.add(sale)
            db.session.commit()
            flash(f"Sale save ho gayi: {counter} — {qty} {item} (₹{total}, {mode}).", "success")
        else:
            flash("Sale save nahi hui: Gaadi ka stock check karein ya shop/quantity sahi bharein.", "error")

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
