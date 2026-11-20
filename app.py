import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'shivshankar_secret_key')

db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vita_agency.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

DEFAULT_PRODUCTS = [
    ("FCM 130 ml", 7.95, 8.50),
    ("FCM 400 ml", 27.00, 28.00),
    ("FCM 1 Ltr", 72.00, 74.00),
    ("FCM 6 Ltr", 394.00, 408.00),
    ("DTM 180 ml", 7.60, 8.00),
    ("DTM 500 ml", 26.00, 27.00),
    ("DTM 6 Ltr", 277.00, 290.00),
    ("Paneer 1 Kg", 353.00, 370.00),
    ("Paneer 200 gm", 72.00, 76.00),
    ("Dahi Cup", 15.00, 16.00),
    ("Dahi 180 gm", 8.50, 9.00),
    ("Dahi 400 gm", 23.00, 26.00),
    ("Dahi 1 Kg", 45.00, 48.00),
    ("Dahi 5 Kg", 235.00, 250.00),
    ("Dahi 15 Kg", 700.00, 750.00),
    ("Namkeen Lassi", 7.90, 8.50),
    ("Chach", 10.00, 11.00),
    ("Kheer", 20.50, 22.00),
    ("Jaljeera", 6.80, 7.50),
    ("Ghee 1 Kg", 0.0, 0.0),
    ("Ghee 2 Kg", 0.0, 0.0),
    ("Ghee 5 Kg", 0.0, 0.0),
    ("Ghee 15 Ltr", 0.0, 0.0),
]


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    route_name = db.Column(db.String(80), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_updated_at = db.Column(db.String(40), nullable=True)


class LocationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    recorded_date = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.String(40), nullable=False)


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


class SavedCounter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    counter_name = db.Column(db.String(100), nullable=False)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_username = db.Column(db.String(80), nullable=False)
    counter_name = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(20), nullable=False)
    sale_date = db.Column(db.String(20), nullable=False)


def sync_existing_counters():
    existing_sales = db.session.query(Sale.driver_username, Sale.counter_name).distinct().all()
    for drv_user, c_name in existing_sales:
        clean_name = (c_name or '').strip()
        if drv_user and clean_name:
            found = SavedCounter.query.filter(
                SavedCounter.driver_username == drv_user,
                db.func.lower(SavedCounter.counter_name) == clean_name.lower()
            ).first()
            if not found:
                db.session.add(SavedCounter(driver_username=drv_user, counter_name=clean_name))


def ensure_schema_and_seed():
    try:
        db.create_all()
        engine = db.engine
        dialect = engine.dialect.name
        if dialect == 'sqlite':
            cols = [row[1] for row in db.session.execute(db.text("PRAGMA table_info(user)")).fetchall()]
            if 'latitude' not in cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN latitude FLOAT"))
            if 'longitude' not in cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN longitude FLOAT"))
            if 'location_updated_at' not in cols:
                db.session.execute(db.text("ALTER TABLE user ADD COLUMN location_updated_at VARCHAR(40)"))
            db.session.commit()
        elif dialect == 'postgresql':
            db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION'))
            db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION'))
            db.session.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS location_updated_at VARCHAR(40)'))
            db.session.commit()

        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password='admin123', role='admin')
            db.session.add(admin_user)

        for name, p_rate, s_rate in DEFAULT_PRODUCTS:
            existing = Product.query.filter(db.func.lower(Product.name) == name.lower()).first()
            if not existing:
                db.session.add(Product(
                    name=name,
                    purchase_rate=p_rate,
                    selling_rate=s_rate,
                    shop_stock=0
                ))
            else:
                if existing.purchase_rate == 0.0 and p_rate > 0.0:
                    existing.purchase_rate = p_rate
                if existing.selling_rate == 0.0 and s_rate > 0.0:
                    existing.selling_rate = s_rate

        sync_existing_counters()
        db.session.commit()
    except Exception:
        db.session.rollback()


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


@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user' in session and session.get('role') == 'driver':
        data = request.get_json(silent=True) or {}
        lat = data.get('latitude')
        lng = data.get('longitude')
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Invalid coordinates'}), 400

        drv = User.query.filter_by(username=session['user'], role='driver').first()
        if drv:
            now_dt = datetime.now()
            now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
            today_str = now_dt.strftime('%Y-%m-%d')

            drv.latitude = lat_f
            drv.longitude = lng_f
            drv.location_updated_at = now_str

            last_log = (
                LocationLog.query
                .filter_by(driver_username=drv.username, recorded_date=today_str)
                .order_by(LocationLog.id.desc())
                .first()
            )
            should_log = True
            if last_log:
                moved = abs(last_log.latitude - lat_f) >= 0.00015 or abs(last_log.longitude - lng_f) >= 0.00015
                same_ts = (last_log.recorded_at == now_str)
                if same_ts or (not moved and last_log.recorded_at[:16] == now_str[:16]):
                    should_log = False

            if should_log:
                db.session.add(LocationLog(
                    driver_username=drv.username,
                    latitude=lat_f,
                    longitude=lng_f,
                    recorded_date=today_str,
                    recorded_at=now_str
                ))

            db.session.commit()
            return jsonify({'ok': True, 'updated_at': drv.location_updated_at})
    return jsonify({'ok': False}), 401


@app.route('/admin')
def admin_dashboard():
    if 'user' in session and session.get('role') == 'admin':
        products = Product.query.order_by(Product.name.asc()).all()
        product_map = {p.name: p for p in products}
        drivers = User.query.filter_by(role='driver').order_by(User.username.asc()).all()
        route_map = {d.username: (d.route_name or '') for d in drivers}
        driver_stocks = DriverStock.query.all()
        all_counters = SavedCounter.query.order_by(SavedCounter.driver_username.asc(), SavedCounter.counter_name.asc()).all()

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
            raw_stock = [ds for ds in driver_stocks if ds.driver_username == d.username and ds.vehicle_stock > 0]

            d_stock = []
            total_return_pur_val = 0.0
            total_return_sell_val = 0.0

            for ds in raw_stock:
                p = product_map.get(ds.item_name)
                p_rate = p.purchase_rate if p else 0.0
                s_rate = p.selling_rate if p else 0.0
                ret_pur = round(ds.vehicle_stock * p_rate, 2)
                ret_sell = round(ds.vehicle_stock * s_rate, 2)

                total_return_pur_val += ret_pur
                total_return_sell_val += ret_sell

                d_stock.append({
                    'item_name': ds.item_name,
                    'vehicle_stock': ds.vehicle_stock,
                    'purchase_rate': p_rate,
                    'selling_rate': s_rate,
                    'return_pur_amount': ret_pur,
                    'return_sell_amount': ret_sell
                })

            d_cash = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'Cash'), 2)
            d_upi = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'UPI'), 2)
            d_udhar = round(sum(s.total_amount for s in d_sales if s.payment_mode == 'Udhar'), 2)

            maps_url = None
            if d.latitude is not None and d.longitude is not None:
                maps_url = f"https://www.google.com/maps?q={d.latitude},{d.longitude}"

            raw_logs = (
                LocationLog.query
                .filter_by(driver_username=d.username, recorded_date=selected_date)
                .order_by(LocationLog.id.desc())
                .limit(12)
                .all()
            )
            loc_history = [
                {
                    'latitude': lg.latitude,
                    'longitude': lg.longitude,
                    'recorded_at': lg.recorded_at,
                    'maps_url': f"https://www.google.com/maps?q={lg.latitude},{lg.longitude}"
                }
                for lg in raw_logs
            ]

            driver_summaries.append({
                'username': d.username,
                'route_name': d.route_name,
                'latitude': d.latitude,
                'longitude': d.longitude,
                'location_updated_at': d.location_updated_at,
                'maps_url': maps_url,
                'loc_history': loc_history,
                'cash': d_cash,
                'upi': d_upi,
                'udhar': d_udhar,
                'sales': d_sales,
                'stock': d_stock,
                'total_return_pur_val': round(total_return_pur_val, 2),
                'total_return_sell_val': round(total_return_sell_val, 2)
            })

        return render_template(
            'admin_dashboard.html',
            products=products,
            drivers=drivers,
            route_map=route_map,
            all_counters=all_counters,
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

        saved_counter_objs = SavedCounter.query.filter_by(driver_username=driver_name).order_by(SavedCounter.counter_name.asc()).all()
        saved_counters = [sc.counter_name for sc in saved_counter_objs]

        total_cash = round(sum(s.total_amount for s in sales if s.payment_mode == 'Cash'), 2)
        total_upi = round(sum(s.total_amount for s in sales if s.payment_mode == 'UPI'), 2)
        total_udhar = round(sum(s.total_amount for s in sales if s.payment_mode == 'Udhar'), 2)

        return render_template(
            'driver_dashboard.html',
            driver_stocks=driver_stocks,
            sales=sales,
            saved_counters=saved_counters,
            saved_counter_objs=saved_counter_objs,
            today_date=today_str,
            total_cash=total_cash,
            total_upi=total_upi,
            total_udhar=total_udhar
        )
    return redirect(url_for('login'))


@app.route('/add_counter', methods=['POST'])
def add_counter():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        new_name = request.form.get('counter_name', '').strip()
        if new_name:
            exists = SavedCounter.query.filter(
                SavedCounter.driver_username == driver_name,
                db.func.lower(SavedCounter.counter_name) == new_name.lower()
            ).first()
            if not exists:
                db.session.add(SavedCounter(driver_username=driver_name, counter_name=new_name))
                db.session.commit()
                flash(f"Counter '{new_name}' permanent save ho gaya.", "success")
            else:
                flash(f"Counter '{new_name}' pehle se saved hai.", "success")
        return redirect(url_for('driver_dashboard'))
    if 'user' in session and session.get('role') == 'admin':
        driver_name = request.form.get('driver_username', '').strip()
        new_name = request.form.get('counter_name', '').strip()
        drv = User.query.filter_by(username=driver_name, role='driver').first()
        if drv and new_name:
            exists = SavedCounter.query.filter(
                SavedCounter.driver_username == driver_name,
                db.func.lower(SavedCounter.counter_name) == new_name.lower()
            ).first()
            if not exists:
                db.session.add(SavedCounter(driver_username=driver_name, counter_name=new_name))
                db.session.commit()
                flash(f"Driver '{driver_name}' ({drv.route_name}) ke liye counter '{new_name}' save ho gaya.", "success")
            else:
                flash(f"Driver '{driver_name}' ke liye counter '{new_name}' pehle se saved hai.", "success")
        else:
            flash("Sahi driver chunein aur counter ka naam bharein.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/rename_counter', methods=['POST'])
def rename_counter():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        old_name = request.form.get('old_counter_name', '').strip()
        new_name = request.form.get('new_counter_name', '').strip()
        if old_name and new_name:
            sc = SavedCounter.query.filter_by(driver_username=driver_name, counter_name=old_name).first()
            if sc:
                sc.counter_name = new_name
                Sale.query.filter_by(driver_username=driver_name, counter_name=old_name).update({'counter_name': new_name})
                db.session.commit()
                flash(f"Counter '{old_name}' ka naam badal kar '{new_name}' ho gaya.", "success")
        return redirect(url_for('driver_dashboard'))
    if 'user' in session and session.get('role') == 'admin':
        counter_id = request.form.get('counter_id')
        new_name = request.form.get('new_counter_name', '').strip()
        sc = SavedCounter.query.get(counter_id) if counter_id else None
        if sc and new_name:
            old_name = sc.counter_name
            sc.counter_name = new_name
            Sale.query.filter_by(driver_username=sc.driver_username, counter_name=old_name).update({'counter_name': new_name})
            db.session.commit()
            flash(f"Counter '{old_name}' ka naam '{new_name}' ho gaya.", "success")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/delete_counter', methods=['POST'])
def delete_counter():
    if 'user' in session and session.get('role') == 'driver':
        driver_name = session['user']
        c_name = request.form.get('counter_name', '').strip()
        sc = SavedCounter.query.filter_by(driver_username=driver_name, counter_name=c_name).first()
        if sc:
            db.session.delete(sc)
            db.session.commit()
            flash(f"Counter '{c_name}' list se delete ho gaya.", "success")
        return redirect(url_for('driver_dashboard'))
    if 'user' in session and session.get('role') == 'admin':
        counter_id = request.form.get('counter_id')
        sc = SavedCounter.query.get(counter_id) if counter_id else None
        if sc:
            cname = sc.counter_name
            db.session.delete(sc)
            db.session.commit()
            flash(f"Counter '{cname}' delete ho gaya.", "success")
        return redirect(url_for('admin_dashboard'))
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


@app.route('/set_godown_stock', methods=['POST'])
def set_godown_stock():
    if 'user' in session and session.get('role') == 'admin':
        item_name = request.form.get('item_name', '').strip()
        new_stock_raw = request.form.get('new_godown_stock', '').strip()
        prod = Product.query.filter_by(name=item_name).first()
        try:
            new_stock = int(new_stock_raw)
        except ValueError:
            new_stock = -1

        if prod and new_stock >= 0:
            prod.shop_stock = new_stock
            db.session.commit()
            flash(f"'{prod.name}' ka godown stock {new_stock} set ho gaya.", "success")
        else:
            flash("Sahi item chunein aur 0 ya usse zyada stock quantity likhein.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/update_product_rates', methods=['POST'])
def update_product_rates():
    if 'user' in session and session.get('role') == 'admin':
        item_name = request.form.get('item_name', '').strip()
        p_rate_raw = request.form.get('purchase_rate', '').strip()
        s_rate_raw = request.form.get('selling_rate', '').strip()

        prod = Product.query.filter_by(name=item_name).first()
        if prod:
            updated = False
            if p_rate_raw != '':
                prod.purchase_rate = float(p_rate_raw)
                updated = True
            if s_rate_raw != '':
                prod.selling_rate = float(s_rate_raw)
                updated = True

            if updated:
                db.session.commit()
                flash(f"'{prod.name}' ke rates update ho gaye (Pur: ₹{prod.purchase_rate} | Sell: ₹{prod.selling_rate}).", "success")
            else:
                flash("Kam se kam ek rate (Purchase ya Selling) bharein.", "error")
        else:
            flash("Saved item nahi mila.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/delete_product', methods=['POST'])
def delete_product():
    if 'user' in session and session.get('role') == 'admin':
        item_name = request.form.get('item_name', '').strip()
        prod = Product.query.filter_by(name=item_name).first()
        if prod:
            DriverStock.query.filter_by(item_name=prod.name).delete()
            db.session.delete(prod)
            db.session.commit()
            flash(f"Item '{prod.name}' saved list se delete ho gaya.", "success")
        else:
            flash("Item nahi mila.", "error")
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
            ret_val = round(return_qty * prod.selling_rate, 2)
            db.session.commit()
            flash(f"{return_qty} {item_name} (₹{ret_val}) wapsi godown mein jama ho gaya.", "success")
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


@app.route('/change_driver_password', methods=['POST'])
def change_driver_password():
    if 'user' in session and session.get('role') == 'admin':
        username = request.form.get('driver_username', '').strip()
        new_password = request.form.get('new_password', '').strip()

        drv = User.query.filter_by(username=username, role='driver').first()
        if drv and new_password:
            drv.password = new_password
            db.session.commit()
            flash(f"Driver '{username}' ka password update ho gaya.", "success")
        else:
            flash("Sahi driver chunein aur naya password bharein.", "error")
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/delete_driver', methods=['POST'])
def delete_driver():
    if 'user' in session and session.get('role') == 'admin':
        username = request.form.get('driver_username', '').strip()
        drv = User.query.filter_by(username=username, role='driver').first()
        if drv:
            DriverStock.query.filter_by(driver_username=username).delete()
            SavedCounter.query.filter_by(driver_username=username).delete()
            LocationLog.query.filter_by(driver_username=username).delete()
            db.session.delete(drv)
            db.session.commit()
            flash(f"Driver ID '{username}' delete ho gayi.", "success")
        else:
            flash("Driver ID nahi mili.", "error")
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
            exists = SavedCounter.query.filter(
                SavedCounter.driver_username == driver_name,
                db.func.lower(SavedCounter.counter_name) == counter.lower()
            ).first()
            if not exists:
                db.session.add(SavedCounter(driver_username=driver_name, counter_name=counter))

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
    ensure_schema_and_seed()


if __name__ == '__main__':
    app.run(debug=True)
