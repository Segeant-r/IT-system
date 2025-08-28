from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///itms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------- MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default='staff')
    password_hash = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(100), default='IT')
    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    @property
    def is_authenticated(self): return True
    @property
    def is_active(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    condition = db.Column(db.String(50), default='Good')
    purchase_date = db.Column(db.Date, nullable=True)
    purchase_cost = db.Column(db.Float, nullable=True)
    vendor = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

class AssetComponent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    serial_number = db.Column(db.String(100), nullable=True)
    condition = db.Column(db.String(50), default='Good')

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_on = db.Column(db.Date, default=date.today)
    returned_on = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default='Assigned')

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    issue = db.Column(db.String(255), nullable=False)
    action_taken = db.Column(db.Text, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    date_reported = db.Column(db.Date, default=date.today)
    date_resolved = db.Column(db.Date, nullable=True)
    vendor = db.Column(db.String(120), nullable=True)

class Expenditure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    doc_type = db.Column(db.String(50), nullable=True)
    doc_number = db.Column(db.String(120), nullable=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    vendor = db.Column(db.String(120), nullable=True)

class RecurringPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    recurrence = db.Column(db.String(30), default='Monthly')
    due_day = db.Column(db.Integer, default=1)
    notify_before_days = db.Column(db.Integer, default=5)
    last_paid_on = db.Column(db.Date, nullable=True)
    vendor = db.Column(db.String(120), nullable=True)

class ISP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    monthly_fee = db.Column(db.Float, nullable=False)
    account_number = db.Column(db.String(120), nullable=True)

class ISPDowntime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    isp_id = db.Column(db.Integer, db.ForeignKey('isp.id'), nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255), nullable=True)

# ---------- AUTH ----------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

# ---------- VIEWS ----------
@app.route('/')
@login_required
def dashboard():
    today = date.today()
    alerts = []
    for rp in RecurringPayment.query.all():
        # establish this/next due date (monthly)
        def last_day(y,m):
            import calendar
            return calendar.monthrange(y,m)[1]
        due = date(today.year, today.month, min(rp.due_day, last_day(today.year, today.month)))
        if due < today:
            y = today.year + (1 if today.month == 12 else 0)
            m = 1 if today.month == 12 else today.month + 1
            due = date(y, m, min(rp.due_day, last_day(y, m)))
        if (due - today).days <= rp.notify_before_days:
            alerts.append({'name': rp.name, 'amount': rp.amount, 'due': due.strftime('%Y-%m-%d')})
    asset_count = Asset.query.count()
    staff_count = User.query.count()
    open_repairs = Repair.query.filter(Repair.date_resolved==None).count()
    month_spend = db.session.query(db.func.coalesce(db.func.sum(Expenditure.amount),0)).filter(
        db.extract('year', Expenditure.date)==today.year,
        db.extract('month', Expenditure.date)==today.month
    ).scalar()
    return render_template('dashboard.html', alerts=alerts, asset_count=asset_count, staff_count=staff_count, open_repairs=open_repairs, month_spend=month_spend)

# Users
@app.route('/users')
@login_required
def users():
    return render_template('users.html', users=User.query.all())

@app.route('/users/add', methods=['POST'])
@login_required
def users_add():
    username = request.form['username']
    full_name = request.form['full_name']
    role = request.form.get('role','staff')
    pw = request.form.get('password','ChangeMe123!')
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
    else:
        u = User(username=username, full_name=full_name, role=role)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        flash('User added', 'success')
    return redirect(url_for('users'))

# Assets
@app.route('/assets')
@login_required
def assets():
    assets = Asset.query.order_by(Asset.category, Asset.tag).all()
    return render_template('assets.html', assets=assets)

@app.route('/assets/add', methods=['POST'])
@login_required
def assets_add():
    a = Asset(
        tag=request.form['tag'],
        name=request.form['name'],
        category=request.form['category'],
        serial_number=request.form.get('serial_number') or None,
        condition=request.form.get('condition','Good'),
        purchase_date=datetime.strptime(request.form.get('purchase_date',''), '%Y-%m-%d').date() if request.form.get('purchase_date') else None,
        purchase_cost=float(request.form.get('purchase_cost') or 0),
        vendor=request.form.get('vendor'),
        notes=request.form.get('notes')
    )
    db.session.add(a)
    db.session.commit()
    flash('Asset added', 'success')
    return redirect(url_for('assets'))

@app.route('/assets/<int:asset_id>')
@login_required
def asset_view(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    components = AssetComponent.query.filter_by(parent_asset_id=asset.id).all()
    current_assignment = Assignment.query.filter_by(asset_id=asset.id, status='Assigned').first()
    history = Assignment.query.filter_by(asset_id=asset.id).order_by(Assignment.assigned_on.desc()).all()
    repairs = Repair.query.filter_by(asset_id=asset.id).order_by(Repair.date_reported.desc()).all()
    users = User.query.order_by(User.full_name).all()
    users_map = {u.id: u for u in users}
    return render_template('asset_view.html', asset=asset, components=components, current_assignment=current_assignment, history=history, repairs=repairs, users=users, users_map=users_map)

@app.route('/assets/<int:asset_id>/components/add', methods=['POST'])
@login_required
def asset_component_add(asset_id):
    c = AssetComponent(parent_asset_id=asset_id, name=request.form['name'], serial_number=request.form.get('serial_number'), condition=request.form.get('condition','Good'))
    db.session.add(c)
    db.session.commit()
    flash('Component added', 'success')
    return redirect(url_for('asset_view', asset_id=asset_id))

# Assignments
@app.route('/assign', methods=['POST'])
@login_required
def assign():
    asset_id = int(request.form['asset_id'])
    user_id = int(request.form['user_id'])
    prev = Assignment.query.filter_by(asset_id=asset_id, status='Assigned').first()
    if prev:
        prev.status = 'Returned'
        prev.returned_on = date.today()
    a = Assignment(asset_id=asset_id, user_id=user_id, status='Assigned', assigned_on=date.today())
    db.session.add(a)
    db.session.commit()
    flash('Asset assigned', 'success')
    return redirect(url_for('asset_view', asset_id=asset_id))

@app.route('/assign/return/<int:assignment_id>')
@login_required
def return_assignment(assignment_id):
    assn = Assignment.query.get_or_404(assignment_id)
    assn.status = 'Returned'
    assn.returned_on = date.today()
    db.session.commit()
    flash('Asset returned', 'info')
    return redirect(url_for('asset_view', asset_id=assn.asset_id))

# Repairs
@app.route('/repairs/add', methods=['POST'])
@login_required
def repairs_add():
    r = Repair(
        asset_id=int(request.form['asset_id']),
        issue=request.form['issue'],
        action_taken=request.form.get('action_taken'),
        cost=float(request.form.get('cost') or 0),
        vendor=request.form.get('vendor')
    )
    db.session.add(r)
    db.session.commit()
    flash('Repair recorded', 'success')
    return redirect(url_for('asset_view', asset_id=r.asset_id))

# Expenditures
@app.route('/expenditures')
@login_required
def expenditures():
    exps = Expenditure.query.order_by(Expenditure.date.desc()).all()
    total = db.session.query(db.func.coalesce(db.func.sum(Expenditure.amount),0)).scalar() or 0
    assets = Asset.query.order_by(Asset.tag).all()
    return render_template('expenditures.html', exps=exps, total=total, assets=assets)

@app.route('/expenditures/add', methods=['POST'])
@login_required
def expenditures_add():
    e = Expenditure(
        date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
        category=request.form['category'],
        description=request.form['description'],
        amount=float(request.form['amount']),
        doc_type=request.form.get('doc_type'),
        doc_number=request.form.get('doc_number'),
        asset_id=int(request.form['asset_id']) if request.form.get('asset_id') else None,
        vendor=request.form.get('vendor')
    )
    db.session.add(e)
    db.session.commit()
    flash('Expenditure recorded', 'success')
    return redirect(url_for('expenditures'))

# Recurring
@app.route('/recurring')
@login_required
def recurring():
    items = RecurringPayment.query.order_by(RecurringPayment.name).all()
    return render_template('recurring.html', items=items, today=date.today())

@app.route('/recurring/add', methods=['POST'])
@login_required
def recurring_add():
    rp = RecurringPayment(
        name=request.form['name'],
        amount=float(request.form['amount']),
        recurrence=request.form.get('recurrence','Monthly'),
        due_day=int(request.form.get('due_day', 1)),
        notify_before_days=int(request.form.get('notify_before_days', 5)),
        vendor=request.form.get('vendor')
    )
    db.session.add(rp)
    db.session.commit()
    flash('Recurring payment added', 'success')
    return redirect(url_for('recurring'))

# ISPs
@app.route('/isps')
@login_required
def isps():
    items = ISP.query.order_by(ISP.name).all()
    return render_template('isps.html', items=items)

@app.route('/isps/add', methods=['POST'])
@login_required
def isps_add():
    isp = ISP(name=request.form['name'], monthly_fee=float(request.form['monthly_fee']), account_number=request.form.get('account_number'))
    db.session.add(isp)
    db.session.commit()
    flash('ISP added', 'success')
    return redirect(url_for('isps'))

@app.route('/isps/<int:isp_id>/downtime/add', methods=['POST'])
@login_required
def downtime_add(isp_id):
    start = datetime.strptime(request.form['start'], '%Y-%m-%dT%H:%M')
    end = datetime.strptime(request.form['end'], '%Y-%m-%dT%H:%M')
    d = ISPDowntime(isp_id=isp_id, start=start, end=end, reason=request.form.get('reason'))
    db.session.add(d)
    db.session.commit()
    flash('Downtime logged', 'success')
    return redirect(url_for('isps'))

# Reports
@app.route('/reports/assets-by-user')
@login_required
def report_assets_by_user():
    rows = db.session.execute(db.text('''
        SELECT u.full_name, a.name, a.serial_number, ass.assigned_on
        FROM assignment ass
        JOIN user u ON u.id = ass.user_id
        JOIN asset a ON a.id = ass.asset_id
        WHERE ass.status = 'Assigned'
        ORDER BY u.full_name, a.name
    '''))
    return render_template('report_assets_by_user.html', rows=rows)

@app.route('/reports/expenditures')
@login_required
def report_expenditures():
    rows = db.session.execute(db.text('''
        SELECT date, category, description, amount, doc_type, doc_number, vendor
        FROM expenditure
        ORDER BY date DESC
    '''))
    total = db.session.query(db.func.coalesce(db.func.sum(Expenditure.amount),0)).scalar() or 0
    return render_template('report_expenditures.html', rows=rows, total=total)

@app.route('/reports/isp-netpay')
@login_required
def report_isp_netpay():
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        next_month = date(today.year+1, 1, 1)
    else:
        next_month = date(today.year, today.month+1, 1)
    month_end = next_month - timedelta(days=1)
    items = []
    for isp in ISP.query.all():
        downs = ISPDowntime.query.filter(ISPDowntime.isp_id==isp.id, ISPDowntime.start>=month_start, ISPDowntime.end<=next_month).all()
        hours = sum([(d.end - d.start).total_seconds()/3600.0 for d in downs])
        total_hours_month = (month_end - month_start).days * 24 + 24
        deduction = isp.monthly_fee * (hours / total_hours_month) if total_hours_month else 0
        net_pay = max(0, isp.monthly_fee - deduction)
        items.append({'name': isp.name, 'monthly_fee': isp.monthly_fee, 'downtime_hours': round(hours,2), 'deduction': round(deduction,2), 'net_pay': round(net_pay,2)})
    return render_template('report_isp_netpay.html', items=items, month=month_start.strftime('%B %Y'))

# ---------- INIT ----------
def ensure_admin():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', full_name='System Administrator', role='admin')
        admin.set_password('ChangeMe123!')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_admin()
    app.run(debug=True)
