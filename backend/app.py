from flask import Flask, request, jsonify, send_from_directory, url_for, render_template, redirect, flash
import smtplib
from flask_pymongo import PyMongo
from pymongo import DESCENDING
from flask_cors import CORS
from flask_mail import Mail, Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_swagger_ui import get_swaggerui_blueprint
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt, check_password_hash
import logging
import pytz

app = Flask(__name__)
# app.config['SERVER_NAME'] = '172.20.238.158:5000'
app.secret_key = 'Kubota'
CORS(app)

app.config['MONGO_URI'] = 'mongodb://localhost:27017/travelAuthority'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'kubotaphportal@gmail.com'
app.config['MAIL_PASSWORD'] = 'pmlh lsuu rjvt ovvi'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mongo = PyMongo(app)
mail = Mail(app)
travel_requests = {}

login_manager = LoginManager(app)
login_manager.login_view = 'login'

bcrypt = Bcrypt(app)

class User(UserMixin):
    def __init__(self, user_id, employee_id, full_name=None, first_name=None, last_name=None, email=None, group=None, groups=None):
        self.id = user_id
        self.employee_id = employee_id
        self.fullName = full_name
        self.firstName = first_name
        self.lastName = last_name
        self.email = email
        self.group = group
        self.groups = groups if groups else ([group] if group else [])

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

@app.template_filter('currency')
def currency_filter(value):
    try:
        return "{:,.2f}".format(float(value))
    except Exception:
        return value

def get_dynamic_approvers(employee_id, division=None, department=None, section=None, group=None, is_international=False):
    """
    Returns a list of approvers (with name, employeeId, rank, email) based on the org chart rules.
    Skips missing roles and avoids duplicates.
    """
    user = mongo.db.users.find_one({'employeeId': employee_id})
    if not user:
        return []


    division = division or user.get('division')
    department = department or user.get('department')
    section = section or user.get('section')
    group = group or user.get('group')
    position = user.get('position', '').lower()

    if (division or '').strip().lower() == 'davao branch':
        approvers = []
        seen_employee_ids = set()

        if position == 'rank & file':
            supervisor = mongo.db.users.find_one({
                'position': {'$regex': '^Supervisor$', '$options': 'i'},
                'division': {'$regex': '^Davao Branch$', '$options': 'i'},
                'department': {'$regex': department or '', '$options': 'i'},
                'section': {'$regex': section or '', '$options': 'i'},
            })
            if supervisor and supervisor.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': supervisor.get('fullName', ''),
                    'employeeId': supervisor.get('employeeId', ''),
                    'position': supervisor.get('position', ''),
                    'email': supervisor.get('email', '')
                })
                seen_employee_ids.add(supervisor.get('employeeId'))

        assistant_manager = mongo.db.users.find_one({
            'position': {'$regex': '^Assistant Manager$', '$options': 'i'},
            'division': {'$regex': '^Davao Branch$', '$options': 'i'},
            'department': {'$regex': department or '', '$options': 'i'},
            'section': {'$regex': section or '', '$options': 'i'},
        })
        if assistant_manager and assistant_manager.get('employeeId') not in seen_employee_ids:
            approvers.append({
                'name': assistant_manager.get('fullName', ''),
                'employeeId': assistant_manager.get('employeeId', ''),
                'position': assistant_manager.get('position', ''),
                'email': assistant_manager.get('email', '')
            })
            seen_employee_ids.add(assistant_manager.get('employeeId'))

        if section:
            section_manager = mongo.db.users.find_one({
                'position': {'$regex': '^Section Manager$', '$options': 'i'},
                'division': {'$regex': '^Davao Branch$', '$options': 'i'},
                'section': {'$regex': section, '$options': 'i'}
            })
            if section_manager and section_manager.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': section_manager.get('fullName', ''),
                    'employeeId': section_manager.get('employeeId', ''),
                    'position': section_manager.get('position', ''),
                    'email': section_manager.get('email', '')
                })
                seen_employee_ids.add(section_manager.get('employeeId'))

        dept_manager = mongo.db.users.find_one({
            'position': {'$regex': '^Department Manager$', '$options': 'i'},
            'division': {'$regex': '^Davao Branch$', '$options': 'i'}
        })
        if dept_manager and dept_manager.get('employeeId') not in seen_employee_ids:
            approvers.append({
                'name': dept_manager.get('fullName', ''),
                'employeeId': dept_manager.get('employeeId', ''),
                'position': dept_manager.get('position', ''),
                'email': dept_manager.get('email', '')
            })
            seen_employee_ids.add(dept_manager.get('employeeId'))

        div_manager = mongo.db.users.find_one({
            'position': {'$regex': '^Division Manager$', '$options': 'i'},
            'division': {'$regex': '^Davao Branch$', '$options': 'i'}
        })
        if div_manager and div_manager.get('employeeId') not in seen_employee_ids:
            approvers.append({
                'name': div_manager.get('fullName', ''),
                'employeeId': div_manager.get('employeeId', ''),
                'position': div_manager.get('position', ''),
                'email': div_manager.get('email', '')
            })
            seen_employee_ids.add(div_manager.get('employeeId'))

        if is_international:
            vp = mongo.db.users.find_one({'position': {'$regex': '^Vice President', '$options': 'i'}})
            president = mongo.db.users.find_one({'position': {'$regex': '^President$', '$options': 'i'}})
            for approver in [vp, president]:
                if approver and approver.get('employeeId') not in seen_employee_ids:
                    approvers.append({
                        'name': approver.get('fullName', ''),
                        'employeeId': approver.get('employeeId', ''),
                        'position': approver.get('position', ''),
                        'email': approver.get('email', '')
                    })
                    seen_employee_ids.add(approver.get('employeeId'))

        return approvers

    division = division or user.get('division')
    department = department or user.get('department')
    section = section or user.get('section')
    group = group or user.get('group')

    position = user.get('position', '').lower()

    if position == 'president':
        approvers = []
        vp = mongo.db.users.find_one({
            'position': {'$regex': '^Vice President', '$options': 'i'}
        })
        if vp:
            approvers.append({
                'name': vp.get('fullName', ''),
                'employeeId': vp.get('employeeId', ''),
                'position': vp.get('position', ''),
                'email': vp.get('email', '')
            })
        return approvers

    if position in ['division manager', 'vice president / division manager', 'vice president']:
        approvers = []
        seen_employee_ids = set()
        vp = mongo.db.users.find_one({
            'position': {'$regex': '^Vice President', '$options': 'i'},
            'employeeId': {'$ne': employee_id}
        })
        president = mongo.db.users.find_one({'position': {'$regex': '^President$', '$options': 'i'}})
        for approver in [vp, president]:
            if approver and approver.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': approver.get('fullName', ''),
                    'employeeId': approver.get('employeeId', ''),
                    'position': approver.get('position', ''),
                    'email': approver.get('email', '')
                })
                seen_employee_ids.add(approver.get('employeeId'))
        return approvers
    approval_chain = [
        ('Supervisor', {'section': section, 'department': department, 'division': division, 'group': group}),
        ('Section Manager', {'section': section, 'department': department, 'division': division,}),
        ('Department Manager', {'department': department, 'division': division}),
        ('Division Manager', {'division': division}),
    ]

    approvers = []
    seen_employee_ids = set()

    if is_international:

        for rank, scope in approval_chain:
            query = {'position': {'$regex': f'^{rank}$', '$options': 'i'}}
            if rank == 'Division Manager' and division in ['Finance', 'ICT & Admin', 'Finance, ICT & Admin']:
                query = {
                    '$or': [
                        {'position': {'$regex': '^Vice President / Division Manager$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}},
                        {'position': {'$regex': '^Division Manager$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}},
                        {'position': {'$regex': '^Vice President$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}}
                    ]
                }
            elif rank == 'Department Manager':
                if department:
                    query['department'] = {'$regex': department, '$options': 'i'}
            else:
                for key, value in scope.items():
                    if value:
                        query[key] = value
            approver = mongo.db.users.find_one(query)
            if approver and approver.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': approver.get('fullName', ''),
                    'employeeId': approver.get('employeeId', ''),
                    'position': approver.get('position', ''),
                    'email': approver.get('email', '')
                })
                seen_employee_ids.add(approver.get('employeeId'))

        vp = mongo.db.users.find_one({
            '$or': [
                {'position': {'$regex': '^Vice President', '$options': 'i'}},
                {'position': {'$regex': '^Vice President / Division Manager', '$options': 'i'}}
            ]
        })
        president = mongo.db.users.find_one({'position': {'$regex': '^President$', '$options': 'i'}})
        for approver in [vp, president]:
            if approver and approver.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': approver.get('fullName', ''),
                    'employeeId': approver.get('employeeId', ''),
                    'position': approver.get('position', ''),
                    'email': approver.get('email', '')
                })
                seen_employee_ids.add(approver.get('employeeId'))
    else:

        for rank, scope in approval_chain:
            query = {'position': {'$regex': f'^{rank}$', '$options': 'i'}}
            if rank == 'Division Manager' and division in ['Finance', 'ICT & Admin', 'Finance, ICT & Admin']:
                query = {
                    '$or': [
                        {'position': {'$regex': '^Vice President / Division Manager$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}},
                        {'position': {'$regex': '^Division Manager$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}},
                        {'position': {'$regex': '^Vice President$', '$options': 'i'}, 'division': {'$regex': division, '$options': 'i'}}
                    ]
                }
            elif rank == 'Department Manager':
                if department:
                    query['department'] = {'$regex': department, '$options': 'i'}
            else:
                for key, value in scope.items():
                    if value:
                        query[key] = value
            approver = mongo.db.users.find_one(query)
            if approver and approver.get('employeeId') not in seen_employee_ids:
                approvers.append({
                    'name': approver.get('fullName', ''),
                    'employeeId': approver.get('employeeId', ''),
                    'position': approver.get('position', ''),
                    'email': approver.get('email', '')
                })
                seen_employee_ids.add(approver.get('employeeId'))
        pass


    approvers = [a for a in approvers if a['employeeId'] != employee_id]

    return approvers

def get_coordinator_for_division(division):
    division = (division or '').strip().lower()
    if division == 'sales & marketing':
        return {
            'employeeId': 'AMC052024-457',
            'name': 'Aiko Cruz'
        }
    elif division == 'customer solutions':
        return {
            'employeeId': 'LOU070124-460',
            'name': 'Liwayway Urbano'
        }
    elif division in ['finance', 'admin', 'ict', 'finance, admin, & ict', 'finance, ict & admin']:
        return {
            'employeeId': 'KSMZ022122-367',
            'name': 'Kwell Zarasate'
        }
    elif division == 'davao branch':
        return {
            'employeeId': 'MDMA120102-094',
            'name': 'Maria Delia Alejandrino'
        }
    else:
        return None

def get_request_data(request_number):
    if request_number.startswith('TOA-'):
        data = mongo.db.travels.find_one({'toaNumber': request_number})
        if data:
            return data, 'travels'
    elif request_number.startswith('OB-'):
        data = mongo.db.officialBusinesses.find_one({'obNumber': request_number})
        if data:
            return data, 'officialBusinesses'
    return None, None

@login_manager.user_loader
def load_user(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user:
        return User(
            str(user['_id']),
            user['employeeId'],
            user.get('fullName'),
            user.get('firstName'),
            user.get('lastName'),
            user.get('email'),
            user.get('group'),
            user.get('groups', None)
        )
    return None

@app.route('/api/current-user')
@login_required
def api_current_user():

    user_group = getattr(current_user, 'group', None)
    user_groups = getattr(current_user, 'groups', None)
    if user_groups:
        groups = user_groups
    elif user_group:
        groups = [user_group]
    else:
        groups = []
    return jsonify({
        'employeeId': current_user.employee_id,
        'name': getattr(current_user, 'fullName', current_user.firstName + ' ' + current_user.lastName),
        'groups': groups,
        'email': current_user.email
    })

@app.route('/api/approvers', methods=['POST'])
@login_required
def get_approvers_api():
    data = request.json
    employee_id = data['employeeId']
    is_international = data.get('isInternational', False)
    approvers = get_dynamic_approvers(employee_id, is_international=is_international)

    return jsonify({'approvers': [
        {
            'name': a['name'],
            'position': a['position'],
            'employeeId': a['employeeId']
        } for a in approvers
    ]})

@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    from datetime import datetime
    if not value:
        return ''
    if isinstance(value, str):
        try:

            value = datetime.fromisoformat(value)
        except Exception:
            return value
    return value.strftime(format)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        employee_id = request.form.get('employeeId')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        position = request.form.get('position')
        divison = request.form.get('division')
        department = request.form.get('department')
        section = request.form.get('section')
        group = request.form.get('group')
        password = request.form.get('password')

        # Create full name from first and last name
        full_name = f"{first_name} {last_name}"

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Check if employee ID already exists
        if mongo.db.users.find_one({'employeeId': employee_id}):
            flash('Employee ID already exists')
            return redirect(url_for('signup'))

        # Insert new user with additional fields
        user_id = mongo.db.users.insert_one({
            'employeeId': employee_id,
            'firstName': first_name,
            'lastName': last_name,
            'fullName': full_name,
            'email': email,
            'position': position,
            'division': divison,
            'department': department,
            'section' : section,
            'group': group,
            'password': hashed_password
        }).inserted_id

        # Log the user in
        user = User(str(user_id), employee_id)
        login_user(user)
        return redirect(url_for('login'))

    return render_template('sign.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        employee_id = request.form.get('employeeId')
        password = request.form.get('password')
        next_url = request.form.get('next') or request.args.get('next') or url_for('homepage')

        user = mongo.db.users.find_one({'employeeId': employee_id})

        if user and bcrypt.check_password_hash(user['password'], password):
            user_obj = User(str(user['_id']), user['employeeId'])
            login_user(user_obj)
            return redirect(next_url)
        else:
            return render_template('sign.html', login_error='Invalid employee ID or password', next=next_url)

    next_url = request.args.get('next', url_for('homepage'))
    return render_template('sign.html', next=next_url)

@app.route('/home')
@login_required
def homepage():
    return render_template('home.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/approval/<toa_number>')
@login_required
def approval_page(toa_number):
    travel = mongo.db.travels.find_one_or_404({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('home'))


    if 'requiresHotel' not in travel:
        travel['requiresHotel'] = False

    if 'requiresTransportation' not in travel:
        travel['requiresTransportation'] = False

    if 'travelMode' not in travel:
        travel['travelMode'] = ''

    if 'transportationTypes' not in travel:
        travel['transportationTypes'] = []
    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    approvers = get_dynamic_approvers(current_user.employee_id)

    formatted_approvers = []
    for approver in approvers:
        formatted_approvers.append({
            'name': approver['name'],
            'position': approver['position'],
            'status': 'Pending',
            'dateApproved': None
        })
    return render_template('approval.html',
                           toa_number=toa_number,
                           current_user=user_data,
                           travel_data=travel,
                           approvers=formatted_approvers)

@app.route('/toa-approval/<toa_number>')
@login_required
def toa_approval_page(toa_number):
    travel = mongo.db.travels.find_one_or_404({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('home'))

    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    approvers = travel.get('approvers', [])


    return render_template('toa_approval.html',
                           toa_number=toa_number,
                           current_user=user_data,
                           travel_data=travel,
                           approvers=approvers)

@app.route('/ob-approval/<ob_number>')
@login_required
def ob_approval_page(ob_number):
    ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
    if not ob:
        flash('Official Business request not found.', 'danger')
        return redirect(url_for('home'))

    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    approvers = ob.get('approvers', [])

    return render_template('ob_approval.html',
                           ob_number=ob_number,
                           current_user=user_data,
                           ob_data=ob,
                           approvers=approvers)

@app.route('/verification/<toa_number>', methods=['GET'])
@login_required
def render_verification_page(toa_number):
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    employee_id = travel.get('employeeId')
    employee_user = mongo.db.users.find_one({'employeeId': employee_id}) if employee_id else None
    division = (employee_user.get('division', '') if employee_user else '').strip()
    coordinator = get_coordinator_for_division(division)

    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('home'))

    return render_template(
        'verification.html',
        toa_number=toa_number,
        current_user=user,
        travel_data=travel,
        coordinator=coordinator
    )

@app.route('/api/time', methods=['POST'])
@login_required
def record_time():
    data = request.json
    action = data.get('action')
    now = datetime.now()
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if action == 'in':
        today = now.date()
        already_in = mongo.db.time_logs.find_one({
            'employeeId': user['employeeId'],
            'action': 'in',
            'timestamp': {
                '$gte': datetime.combine(today, datetime.min.time()),
                '$lte': datetime.combine(today, datetime.max.time())
            }
        })
        if already_in:
            return jsonify({'error': 'Already timed in today'}), 400

    record = {
        'employeeId': user['employeeId'],
        'fullName': user.get('fullName', ''),
        'action': action,
        'timestamp': now
    }
    mongo.db.time_logs.insert_one(record)
    return jsonify({'message': f"Time {'In' if action == 'in' else 'Out'} recorded at {now.strftime('%Y-%m-%d %H:%M:%S')}"})

@app.route('/api/time-in-status', methods=['GET'])
@login_required
def time_in_status():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    today = datetime.now().date()
    time_in = mongo.db.time_logs.find_one({
        'employeeId': user['employeeId'],
        'action': 'in',
        'timestamp': {
            '$gte': datetime.combine(today, datetime.min.time()),
            '$lte': datetime.combine(today, datetime.max.time())
        }
    })
    return jsonify({'timed_in_today': bool(time_in)})

@app.route('/api/time-out-status', methods=['GET'])
@login_required
def time_out_status():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    today = datetime.now().date()
    time_out = mongo.db.time_logs.find_one({
        'employeeId': user['employeeId'],
        'action': 'out',
        'timestamp': {
            '$gte': datetime.combine(today, datetime.min.time()),
            '$lte': datetime.combine(today, datetime.max.time())
        }
    })
    return jsonify({'timed_out_today': bool(time_out)})

@app.route('/toa')
@login_required
def home():
    # Get current user info from database
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    print(f"Current user: {user}")
    approvers = get_dynamic_approvers(current_user.employee_id)
    print(f"Approvers found: {approvers}")

    formatted_approvers = []
    for approver in approvers:
        formatted_approvers.append({
            'name': approver['name'],
            'position': approver['position'],
            'status': 'Pending',
            'dateApproved': None
        })

    # Pass user data to the template
    return render_template('index.html', user_data=user, approvers=formatted_approvers)

@app.route('/official-business')
@login_required
def official_business():
    user_id = current_user.id  # however you get user info
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    approvers = get_dynamic_approvers(current_user.employee_id)

    formatted_approvers = []
    for approver in approvers:
        formatted_approvers.append({
            'name': approver['name'],
            'position': approver['position'],
            'status': 'Pending',
            'dateApproved': None
        })

    return render_template('official_business.html', user_data=user, approvers=formatted_approvers)

@app.route('/api/travel', methods=['POST'])
def create_travel():
    data = request.json

    last_travel = mongo.db.travels.find_one(sort=[('toaNumber', DESCENDING)])
    last_toa_number = int(last_travel['toaNumber'].split('-')[1]) if last_travel else 0
    new_toa_number = f"TOA-{str(last_toa_number + 1).zfill(5)}"
    is_international = data.get('isInternational', False)


    try:
        date_filed = datetime.strptime(data['dateFiled'], '%Y-%m-%dT%H:%M')  # Expecting 'YYYY-MM-DDTHH:MM'
    except ValueError:
        date_filed = datetime.strptime(data['dateFiled'], '%Y-%m-%d')  # If time is missing, store as midnight
    try:
        approvers = get_dynamic_approvers(data['employeeId'], is_international=is_international)
        new_travel = {
            'toaNumber': new_toa_number,
            'dateFiled': date_filed,
            'travelType': data['travelType'],
            'isInternational': is_international,
            'employeeId': data['employeeId'],
            'employee': data['employee'],
            'department': data['department'],
            'position': data['position'],
            'startDate': datetime.strptime(data['startDate'], '%Y-%m-%d'),
            'endDate': datetime.strptime(data['endDate'], '%Y-%m-%d'),
            'origin': data['origin'],
            'destinations': data['destinations'],
            'purpose': data['purpose'],
            'approvalStatus': 'Pending',
            'remarks': data['remarks'],
            'travelMode': data.get('travelMode', 'air'),
            'paymentMethod': data.get('paymentMethod', ''),
            'requiresHotel': data.get('requiresHotel', False),
            'requiresTransportation': data.get('requiresTransportation', False),
            'transportationTypes': data.get('transportationTypes', []),
            'carRentalRequested': data.get('carRentalRequested', False),
            'requiresVerification': data.get('requiresHotel', False),
            'requiresCashAdvance': data.get('requiresCashAdvance', False),
            'itinerary': data.get('itinerary', []),  # Add itinerary data
            'approvers': [
                {
                    'name': a['name'],
                    'employeeId': a['employeeId'],
                    'position': a['position'],
                    'status': 'Pending',
                    'dateApproved': None
                } for a in approvers
            ]
        }

        transportation_types = data.get('transportationTypes', [])
        if 'common-car' in transportation_types:
            hr_user = mongo.db.users.find_one({'position': {'$regex': '^HR', '$options': 'i'}, 'email': {'$exists': True, '$ne': ''}})
            hr_email = hr_user['email'] if hr_user else 'charlieho611@gmail.com'
            msg = Message(
                subject='Common Car Request Notification',
                sender='kubotaphportal@gmail.com',
                recipients=[hr_email]
            )
            msg.body = (
                f"Employee {data.get('employee')} (ID: {data.get('employeeId')}) has requested a Common Car for travel.\n"
                f"TOA Number: {new_toa_number}\n"
                f"Travel Dates: {data.get('startDate')} to {data.get('endDate')}\n"
                f"Purpose: {data.get('purpose')}\n"
                f"Please coordinate the common car arrangement."
            )
            mail.send(msg)

    except KeyError as e:
        return jsonify({'error': f'Missing field: {e.args[0]}'}), 400

    result = mongo.db.travels.insert_one(new_travel)

    employee_user = mongo.db.users.find_one({'employeeId': data.get('employeeId')})
    if employee_user and 'email' in employee_user:
        msg = Message(
            subject=f'Travel Order Submitted: {new_travel["toaNumber"]}',
            sender='kubotaphportal@gmail.com',
            recipients=[employee_user['email']]
        )
        msg.body = f"""
Dear {employee_user.get('fullName', data.get('employee'))},

Your travel order (TOA: {new_travel['toaNumber']}) has been submitted successfully.

Travel Details:
- Origin: {data.get('origin')}
- Destination: {', '.join(data.get('destinations', []))}
- Start Date: {data.get('startDate')}
- End Date: {data.get('endDate')}
- Purpose: {data.get('purpose')}
{"This is an INTERNATIONAL travel." if data.get('isInternational') else ""}
You will be notified once your request is reviewed by the approvers.

Best regards,
Travel Authority System
"""
    mail.send(msg)

    response = {
        'toaNumber': new_toa_number,
        'requiresCashAdvance': new_travel['requiresCashAdvance']
    }

    # Only include redirect URL if cash advance is required
    if new_travel['requiresCashAdvance']:
        response['redirect'] = url_for('render_cash_advance_form', toa_number=new_toa_number)
    else:
        response['redirect'] = url_for('homepage')
        if approvers:
            first_approver = approvers[0]
            msg = Message(
                'New Travel Authority Request',
                sender='kubotaphportal@gmail.com',
                recipients=[first_approver['email']]
            )
        approval_link = url_for('login', next=url_for('toa_approval_page', toa_number=new_toa_number), _external=True)
        msg.body = f"""
            Dear {first_approver['name']},

            A new travel authority request has been submitted by {data['employee']}.
            Travel Details:
            - Origin: {data['origin']}
            - Destination: {data['destinations']}
            - Start Date: {data['startDate']}
            - End Date: {data['endDate']}

            Please review and approve/reject it using the following link:
            {approval_link}
            """
        mail.send(msg)
    return jsonify(response), 201

@app.route('/api/official-business', methods=['POST'])
@login_required
def create_official_business():
    data = request.json

    last_ob = mongo.db.officialBusinesses.find_one(
        sort=[('obNumber', -1)]
    )
    if last_ob and 'obNumber' in last_ob:
        last_number = int(last_ob['obNumber'].split('-')[1])
    else:
        last_number = 0
    new_ob_number = f"OB-{str(last_number + 1).zfill(5)}"

    try:
        date_filed_str = data['dateFiled']
        if 'T' in date_filed_str:
            date_filed = datetime.strptime(date_filed_str, '%Y-%m-%dT%H:%M')
        else:
            date_filed = datetime.strptime(date_filed_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid dateFiled format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM'}), 400

    approvers = get_dynamic_approvers(data['employeeId'])
    new_ob = {
        'obNumber': new_ob_number,
        'dateFiled': datetime.strptime(data['dateFiled'], '%Y-%m-%dT%H:%M'),
        'employeeId': data['employeeId'],
        'employee': data['employee'],
        'department': data['department'],
        'position': data['position'],
        'startDate': datetime.strptime(data['startDate'], '%Y-%m-%d'),
        'endDate': datetime.strptime(data['endDate'], '%Y-%m-%d'),
        'origin': data['origin'],
        'destinations': data['destinations'],
        'purpose': data['purpose'],
        'approvalStatus': 'Pending',
        'remarks': data.get('remarks', ''),
        'requiresTransportation': data.get('requiresTransportation', False),
        'transportationTypes': data.get('transportationTypes', []),
        'paymentOption': data.get('paymentOption'),
        'requiresCashAdvance': data.get('requiresCashAdvance', False),
        'approvers': [
            {
                'name': a['name'],
                'employeeId': a['employeeId'],
                'position': a['position'],
                'status': 'Pending',
                'dateApproved': None
            } for a in approvers
        ]
    }

    transportation_types = data.get('transportationTypes', [])
    if 'common-car' in transportation_types:
                hr_user = mongo.db.users.find_one({'position': {'$regex': '^HR', '$options': 'i'}, 'email': {'$exists': True, '$ne': ''}})
                hr_email = hr_user['email'] if hr_user else 'charlieho611@gmail.com'
                msg = Message(
                    subject='Common Car Request Notification',
                    sender='kubotaphportal@gmail.com',
                    recipients=[hr_email]
                )
                msg.body = (
                    f"Employee {data.get('employee')} (ID: {data.get('employeeId')}) has requested a Common Car for travel.\n"
                    f"TOA Number: {new_ob_number}\n"
                    f"Travel Dates: {data.get('startDate')} to {data.get('endDate')}\n"
                    f"Purpose: {data.get('purpose')}\n"
                    f"Please coordinate the common car arrangement."
                )
                mail.send(msg)

    result = mongo.db.officialBusinesses.insert_one(new_ob)
    ob_employee_user = mongo.db.users.find_one({'employeeId': data.get('employeeId')})
    if ob_employee_user and 'email' in ob_employee_user:
        msg = Message(
            subject=f'Official Business Submitted: {new_ob_number}',
            sender='kubotaphportal@gmail.com',
            recipients=[ob_employee_user['email']]
        )
        msg.body = f"""
    Dear {ob_employee_user.get('fullName', data.get('employee'))},

    Your Official Business request (OB: {new_ob_number}) has been submitted successfully.

    Details:
    - Origin: {data.get('origin')}
    - Destination: {', '.join(data.get('destinations', []))}
    - Start Date: {data.get('startDate')}
    - End Date: {data.get('endDate')}
    - Purpose: {data.get('purpose')}

    You will be notified once your request is reviewed by the approvers.

    Best regards,
    Travel Authority System
    """
        mail.send(msg)

    if new_ob['approvers']:
        first_approver = new_ob['approvers'][0]
        approver_user = mongo.db.users.find_one({'employeeId': first_approver['employeeId']})
        if approver_user and 'email' in approver_user:
            approval_link = url_for('login', next=url_for('ob_approval_page', ob_number=new_ob_number), _external=True)
            msg = Message(
                subject=f'Official Business Approval Needed (OB #{new_ob_number})',
                sender='kubotaphportal@gmail.com',
                recipients=[approver_user['email']]
            )
            msg.body = f"""Dear {first_approver['name']},

You have a new Official Business request (OB #{new_ob_number}) pending your approval.
Employee: {new_ob.get('employeeName', new_ob.get('employee'))}
Purpose: {new_ob.get('purpose')}

Please review and approve/reject using the following link:
{approval_link}

Best regards,
Travel Authority System
"""
            mail.send(msg)
    return jsonify({'message': 'Official Business approved and employee notified.'}), 201

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/api/travel', methods=['GET'])
def get_travels():
    travels = mongo.db.travels.find()
    result = []
    for travel in travels:
        travel['_id'] = str(travel['_id'])
        travel['dateFiled'] = travel['dateFiled'].strftime('%Y-%m-%d %H:%M')
        travel['startDate'] = travel['startDate'].strftime('%Y-%m-%d')
        travel['endDate'] = travel['endDate'].strftime('%Y-%m-%d')
        result.append(travel)
    return jsonify(result)

@app.route('/api/travel/<toa_number>', methods=['GET'])
def get_travel(toa_number):
    try:
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Convert MongoDB ObjectId and dates
        travel['_id'] = str(travel['_id'])


        # Handle other date fields if needed
        date_fields = ['dateFiled', 'startDate', 'endDate']
        for field in date_fields:
            if travel.get(field):
                if isinstance(travel[field], datetime):
                    travel[field] = travel[field].isoformat()

        return jsonify(travel)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
from flask import request, jsonify
from flask_login import login_required, current_user

@app.route('/api/request-car-rental', methods=['POST'])
@login_required
def request_car_rental():
    data = request.json
    toa_number = data.get('toaNumber')
    if not toa_number:
        return jsonify({'error': 'TOA number is required for car rental approval link.'}), 400
    employee_id = data.get('employeeId')
    employee_name = data.get('employeeName')
    approval_link = url_for('login', next=url_for('car_rental_approval', toa_number=toa_number), _external=True)
    msg = Message(
        subject='Car Rental Request',
        sender='kubotaphportal@gmail.com',
        recipients=['charlieho611@gmail.com']
    )
    msg.body = (
        f"Employee {employee_name} (ID: {employee_id}) has requested a car rental via the TOA system.\n"
        f"View and approve/reject the request here: {approval_link}"
    )
    mail.send(msg)
    return jsonify({'message': 'HR notified.'})

@app.route('/api/official-business/<ob_number>', methods=['GET'])
@login_required
def get_official_business_details(ob_number):
    try:
        ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
        if not ob:
            return jsonify({'error': 'Official Business request not found'}), 404

        ob['_id'] = str(ob['_id'])

        date_fields = ['dateFiled', 'startDate', 'endDate']
        for field in date_fields:
            if ob.get(field) and isinstance(ob[field], datetime):
                ob[field] = ob[field].isoformat()

        if 'approvers' in ob and isinstance(ob['approvers'], list):
            for approver_item in ob['approvers']: # Renamed loop variable
                if approver_item.get('dateApproved') and isinstance(approver_item['dateApproved'], datetime):
                    approver_item['dateApproved'] = approver_item['dateApproved'].isoformat()

        return jsonify(ob)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/official-business/<ob_number>/status', methods=['GET'])
@login_required
def get_ob_approval_status_api(ob_number): # Renamed function
    ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number}, {'approvers': 1, 'approvalStatus': 1, 'requiresCashAdvance': 1})
    if not ob:
        return jsonify({'error': 'Official Business request not found'}), 404
    # Ensure all necessary fields are present, providing defaults if not
    response_data = {
        'approvers': ob.get('approvers', []),
        'approvalStatus': ob.get('approvalStatus', 'Pending'),
        'requiresCashAdvance': ob.get('requiresCashAdvance', False)
    }
    return jsonify(response_data)


# API Endpoint to Approve Official Business
@app.route('/api/official-business/<ob_number>/approve', methods=['POST'])
@login_required
def approve_official_business_api(ob_number): # Renamed function
    try:
        user_id = current_user.id
        user_data_db = mongo.db.users.find_one({'_id': ObjectId(user_id)}) # Renamed
        if not user_data_db:
            return jsonify({'error': 'User not found'}), 404

        approver_name = user_data_db.get('fullName')
        employee_id = user_data_db.get('employeeId')

        ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
        if not ob:
            return jsonify({'error': 'Official Business request not found'}), 404

        approvers_list = ob.get('approvers', []) # Renamed
        timestamp = datetime.utcnow() # Store as datetime object

        approver_found = False
        for approver_item in approvers_list: # Renamed loop variable
            if approver_item.get('employeeId') == employee_id: # Prioritize employeeId match
                if approver_item.get('status') == 'Pending':
                    approver_item['status'] = 'Approved'
                    approver_item['dateApproved'] = timestamp
                    approver_found = True
                elif approver_item.get('status') == 'Approved':
                     return jsonify({'message': 'Request already approved by you.', 'already_approved': True}), 200
                elif approver_item.get('status') == 'Rejected':
                     return jsonify({'error': 'Request already rejected by you. Cannot approve.', 'already_rejected': True}), 400
                break
            elif approver_item.get('name') == approver_name and approver_item.get('status') == 'Pending': # Fallback to name if no employeeId match and status is pending
                approver_item['status'] = 'Approved'
                approver_item['dateApproved'] = timestamp
                approver_found = True
                break


        if not approver_found:
            # Check if already decided
            current_approver_state = next((a for a in approvers_list if a.get('employeeId') == employee_id or a.get('name') == approver_name), None)
            if current_approver_state and current_approver_state.get('status') != 'Pending':
                 return jsonify({'message': f"You have already {current_approver_state.get('status').lower()} this request.", 'already_decided': True}), 200
            return jsonify({'error': 'You are not authorized or not pending to approve this request.'}), 403

        mongo.db.officialBusinesses.update_one(
            {'obNumber': ob_number},
            {'$set': {'approvers': approvers_list}}
        )

        next_approver = next((a for a in approvers_list if a['status'] == 'Pending'), None)
        if next_approver:
            next_approver_user = mongo.db.users.find_one({'employeeId': next_approver['employeeId']})
            if next_approver_user and 'email' in next_approver_user:
                approval_link = url_for('login', next=url_for('ob_approval_page', ob_number=ob_number), _external=True)
                msg = Message(
                    subject=f'Action Required: Official Business Approval (OB #{ob_number})',
                    sender='kubotaphportal@gmail.com',
                    recipients=[next_approver_user['email']]
                )
                msg.body = f"""Dear {next_approver['name']},

You have a new Official Business request (OB #{ob_number}) pending your approval.
Employee: {ob.get('employeeName', ob.get('employee'))}
Purpose: {ob.get('purpose')}

Please review and approve/reject using the following link:
{approval_link}

Best regards,
Travel Authority System
"""
                mail.send(msg)

        all_approved = all(a['status'] == 'Approved' for a in approvers_list)
        if all_approved:
            mongo.db.officialBusinesses.update_one(
                {'obNumber': ob_number},
                {'$set': {'approvalStatus': 'Approved'}}
            )
            # Notify employee of final approval
            ob_employee_user = mongo.db.users.find_one({'employeeId': ob.get('employeeId')})
            if ob_employee_user and 'email' in ob_employee_user:
                report_link = url_for('login', next=url_for('ob_final_report', ob_number=ob_number), _external=True)
                msg = Message(
                    subject=f'Your Official Business (OB #{ob_number}) is Approved',
                    sender='kubotaphportal@gmail.com',
                    recipients=[ob_employee_user['email']]
                )

                msg.body = f"""Dear {ob.get('employeeName', ob.get('employee', 'Employee'))},

Your Official Business request (OB #{ob_number}) has been fully approved.

You can view and print your final report here (login required):
{report_link}

Best regards,
Travel Authority System
"""
                mail.send(msg)

        # Generic approval notification to employee for this step
        ob_employee_user_step = mongo.db.users.find_one({'employeeId': ob.get('employeeId')})
        if ob_employee_user_step and 'email' in ob_employee_user_step:
            msg_step = Message(
                subject=f'Official Business Update (OB #{ob_number}) - Approved by {approver_name}',
                sender='kubotaphportal@gmail.com',
                recipients=[ob_employee_user_step['email']]
            )
            msg_step.body = f"""Dear {ob.get('employeeName', ob.get('employee', 'Employee'))},

Your Official Business request (OB #{ob_number}) has been approved by {approver_name}.
It will now proceed to the next approver if any, or be marked as fully approved.

Best regards,
Travel Authority System
"""
            mail.send(msg_step)


        return jsonify({'message': f'Official Business request approved by {approver_name}', 'timestamp': timestamp.isoformat()})

    except Exception as e:
        print(f"Error in approve_official_business_api: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API Endpoint to Reject Official Business
@app.route('/api/official-business/<ob_number>/reject', methods=['POST'])
@login_required
def reject_official_business_api(ob_number): # Renamed function
    try:
        data = request.json
        user_id = current_user.id
        remarks_text = data.get('remarks', '') # Renamed
        if not remarks_text:
            return jsonify({'error': 'Remarks are required for rejection.'}), 400

        user_data_db = mongo.db.users.find_one({'_id': ObjectId(user_id)}) # Renamed
        if not user_data_db:
            return jsonify({'error': 'User not found'}), 404

        approver_name = user_data_db.get('fullName')
        employee_id = user_data_db.get('employeeId')

        ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
        if not ob:
            return jsonify({'error': 'Official Business request not found'}), 404

        approvers_list = ob.get('approvers', []) # Renamed
        timestamp = datetime.utcnow() # Store as datetime object

        approver_found = False
        for approver_item in approvers_list: # Renamed loop variable
            if approver_item.get('employeeId') == employee_id: # Prioritize employeeId match
                if approver_item.get('status') == 'Pending':
                    approver_item['status'] = 'Rejected'
                    approver_item['dateApproved'] = timestamp
                    approver_item['remarks'] = remarks_text
                    approver_found = True
                elif approver_item.get('status') == 'Rejected':
                    return jsonify({'message': 'Request already rejected by you.', 'already_rejected': True}), 200
                elif approver_item.get('status') == 'Approved':
                    return jsonify({'error': 'Request already approved by you. Cannot reject.', 'already_approved': True}), 400
                break
            elif approver_item.get('name') == approver_name and approver_item.get('status') == 'Pending': # Fallback to name
                approver_item['status'] = 'Rejected'
                approver_item['dateApproved'] = timestamp
                approver_item['remarks'] = remarks_text
                approver_found = True
                break

        if not approver_found:
            current_approver_state = next((a for a in approvers_list if a.get('employeeId') == employee_id or a.get('name') == approver_name), None)
            if current_approver_state and current_approver_state.get('status') != 'Pending':
                 return jsonify({'message': f"You have already {current_approver_state.get('status').lower()} this request.", 'already_decided': True}), 200
            return jsonify({'error': 'You are not authorized or not pending to reject this request.'}), 403

        mongo.db.officialBusinesses.update_one(
            {'obNumber': ob_number},
            {'$set': {'approvers': approvers_list, 'approvalStatus': 'Rejected', 'remarks': remarks_text}} # Set overall status and main remarks
        )

        # Notify employee of rejection
        ob_employee_user = mongo.db.users.find_one({'employeeId': ob.get('employeeId')})
        if ob_employee_user and 'email' in ob_employee_user:
            msg = Message(
                subject=f'Your Official Business (OB #{ob_number}) was Rejected',
                sender='kubotaphportal@gmail.com',
                recipients=[ob_employee_user['email']]
            )
            msg.body = f"""Dear {ob.get('employeeName', ob.get('employee', 'Employee'))},

Your Official Business request (OB #{ob_number}) has been rejected by {approver_name}.
Remarks: {remarks_text}

Please contact the approver or your supervisor for more details.

Best regards,
Travel Authority System
"""
            mail.send(msg)

        return jsonify({'message': f'Official Business request rejected by {approver_name}', 'timestamp': timestamp.isoformat()})

    except Exception as e:
        print(f"Error in reject_official_business_api: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/cash-advance-approval/<toa_number>')
@login_required
def cash_advance_approval_page(toa_number):
    # Fetch TOA data
    travel = mongo.db.travels.find_one_or_404({'toaNumber': toa_number})

    # Fetch cash advance data
    cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number}, sort=[('requestDate', DESCENDING)])
    if not cash_advance:
        flash('No cash advance found for this TOA.', 'warning')
        return redirect(url_for('approval_page', toa_number=toa_number))

    # Fetch approver data
    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    approvers = cash_advance.get('approvers', [])

    return render_template(
        'cash_advance_approval.html',
        toa_number=toa_number,
        current_user=user_data,
        travel_data=travel,
        cash_advance=cash_advance,
        approvers=approvers
    )

@app.route('/api/travel/<toa_number>/approve', methods=['POST'])
@login_required
def approve_travel(toa_number):
    try:
        data = request.json  # Ensure the request contains JSON data
        user_id = current_user.id  # Use the logged-in user's ID


        # Retrieve the user info from the users collection
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        approver_name = user.get('fullName')
        employee_id = user.get('employeeId')

        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        approvers = travel.get('approvers', [])
        timestamp = datetime.utcnow().isoformat() + 'Z'

        # Debug
        print(f"Looking for approver with ID: {employee_id} or name: {approver_name}")
        print(f"Available approvers: {approvers}")

        approver_found = False
        matched_approver = None
        for approver in approvers:
            if approver.get('employeeId') == employee_id:
                approver['status'] = 'Approved'
                approver['dateApproved'] = timestamp
                approver_found = True
                matched_approver = approver
                break

            # Then try matching by name (without title)
            approver_name_without_title = approver.get('name', '').replace('Mr. ', '').replace('Ms. ', '')
            if approver_name_without_title == approver_name:
                approver['status'] = 'Approved'
                approver['dateApproved'] = timestamp
                approver_found = True
                matched_approver = approver
                break

        if not approver_found:
            return jsonify({'error': f'You are not authorized to approve this request. Your ID: {employee_id}, Name: {approver_name}'}), 403

        # Update in database - careful with the query
        if matched_approver.get('employeeId'):
            # If we matched by employeeId
            mongo.db.travels.update_one(
                {'toaNumber': toa_number, 'approvers.employeeId': matched_approver['employeeId']},
                {'$set': {'approvers.$.status': 'Approved', 'approvers.$.dateApproved': timestamp}}
            )
        else:
            # If we matched by name
            mongo.db.travels.update_one(
                {'toaNumber': toa_number, 'approvers.name': matched_approver['name']},
                {'$set': {'approvers.$.status': 'Approved', 'approvers.$.dateApproved': timestamp}}
            )

        next_approver = next((a for a in approvers if a['status'] == 'Pending'), None)
        if next_approver:
            next_approver_user = mongo.db.users.find_one({'employeeId': next_approver['employeeId']})
            if next_approver_user and 'email' in next_approver_user:
                approval_link = url_for('login', next=url_for('toa_approval_page', toa_number=toa_number), _external=True)
                msg = Message(
                    subject=f'Action Required: Travel Authority Approval (TOA: {toa_number})',
                    sender='kubotaphportal@gmail.com',
                    recipients=[next_approver_user['email']]
                )
                msg.body = f"""Dear {next_approver['name']},

            A new travel authority request has been submitted by {travel.get('employee', 'Employee')}.
            Travel Details:
            - Origin: {travel.get('origin', 'Not specified')}
            - Destination: {', '.join(travel.get('destinations', []))}
            - Start Date: {travel.get('startDate')}
            - End Date: {travel.get('endDate')}

            Please review and approve/reject it using the following link:
            {approval_link}
"""
                mail.send(msg)
        # Check if all approvers have approved
        all_approved = all(a['status'] == 'Approved' for a in approvers)
        # Inside your approve_travel function, replace the section after checking all_approved:
        if all_approved:
            mongo.db.travels.update_one(
                {'toaNumber': toa_number},
                {'$set': {'approvalStatus': 'Approved'}}
            )

            # Check if hotel is required before sending verification email
            if travel.get('requiresHotel', False):
                employee_id = travel.get('employeeId')
                employee_user = mongo.db.users.find_one({'employeeId': employee_id}) if employee_id else None
                division = (employee_user.get('division', '') if employee_user else '').strip()
                coordinator = get_coordinator_for_division(division)
                coordinator_email = None
                coordinator_name = 'Coordinator'
                if coordinator:
                    coordinator_user = mongo.db.users.find_one({'employeeId': coordinator['employeeId']})
                    if coordinator_user and 'email' in coordinator_user:
                        coordinator_email = coordinator_user['email']
                        coordinator_name = coordinator_user.get('fullName', coordinator['name'])
                if coordinator_email:
                    approval_link = url_for('login', next=url_for('render_verification_page', toa_number=toa_number), _external=True)
                    msg = Message(
                        'TOA Ready for Verification',
                        sender='kubotaphportal@gmail.com',
                        recipients=[coordinator_email]
                    )
                    msg.body = f"""
            Dear {coordinator_name},

            The Travel Authority Request with TOA Number {toa_number} has been approved by all approvers.
            Please proceed with the verification process.

            You can access the verification page using the following link:
            {approval_link}

            Thank you.
            """
                    mail.send(msg)
            else:
                employee_id = travel.get('employeeId')
                employee_user = mongo.db.users.find_one({'employeeId': employee_id})

                if employee_user and 'email' in employee_user:
                    report_link = url_for('login', next=url_for('toa_report', toa_number=toa_number), _external=True)
                    msg = Message(
                        subject=f'Your Travel Order is Approved: {toa_number}',
                        sender='kubotaphportal@gmail.com',
                        recipients=[employee_user['email']]
                    )

                    # Format dates for display
                    start_date = travel.get('startDate')
                    end_date = travel.get('endDate')
                    if isinstance(start_date, datetime):
                        start_date = start_date.strftime('%B %d, %Y')
                    if isinstance(end_date, datetime):
                        end_date = end_date.strftime('%B %d, %Y')


                    msg.body = f"""
        Dear {travel.get('employee', 'Employee')},

        Your travel order (TOA: {toa_number}) has been approved by all approvers.

        Travel Period: {start_date} to {end_date}
        Destination(s): {', '.join(travel.get('destinations', []))}

        You can view and print your final report here (login required):
        {report_link}

        Best regards,
        Travel Authority System
        """
                    mail.send(msg)

        # Fetch the user's email from the database
        travel_user = mongo.db.users.find_one({'employeeId': travel['employeeId']})
        if not travel_user:
            return jsonify({'error': 'User not found'}), 404
        user_email = travel_user['email']

        # Send an email notification to the user
        msg = Message(
            'Travel Request Approved',
            sender='kubotaphportal@gmail.com',
            recipients=[user_email]
        )
        msg.body = f"""
        Dear {travel.get('employee', 'Employee')},

        Your travel request has been approved by {approver_name}.
        Travel Details:
        - Origin: {travel['origin']}
        - Destination: {', '.join(travel['destinations'])}
        - Start Date: {travel['startDate']}
        - End Date: {travel['endDate']}

        Please check the system for further updates.

        Best regards,
        Travel Authority System
        """
        mail.send(msg)


        return jsonify({'message': f'Travel request approved by {approver_name}', 'timestamp': timestamp})

    except Exception as e:
        print(f"Error in approve_travel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/travel/<toa_number>/reject', methods=['POST'])
@login_required
def reject_travel(toa_number):
    try:
        data = request.json  # Ensure the request contains JSON data
        user_id = current_user.id  # Use the logged-in user's ID
        remarks = data.get('remarks', '')

        # Retrieve the username from the users collection
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        approver_name = user.get('fullName')
        employee_id = user.get('employeeId')

        # Retrieve the travel request from the database
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Find the specific approver and update their status
        approvers = travel.get('approvers', [])
        timestamp = datetime.utcnow().isoformat() + 'Z'  # ISO format with timezone

        approver_found = False
        for approver in approvers:
            if (approver.get('employeeId') == employee_id) or (approver['name'] == approver_name):
                approver['status'] = 'Rejected'
                approver['dateApproved'] = timestamp
                approver['remarks'] = remarks
                approver_found = True
                break

        if not approver_found:
            return jsonify({'error': f'Approver {approver_name} not found'}), 404

        # Update the approver's status in the database
        mongo.db.travels.update_one(
            {'toaNumber': toa_number, 'approvers.employeeId': approver.get('employeeId')},
            {'$set': {'approvers.$.status': 'Rejected', 'approvers.$.dateApproved': timestamp, 'approvers.$.remarks': remarks}}
        )

        # Set the overall approval status to Rejected
        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {'approvalStatus': 'Rejected'}}
        )

        # Fetch the user's email from the database
        travel_user = mongo.db.users.find_one({'employeeId': travel['employeeId']})
        if not travel_user:
            return jsonify({'error': 'User not found'}), 404
        user_email = travel_user['email']

        # Send an email notification to the user
        msg = Message(
            'Travel Request Rejected',
            sender='kubotaphportal@gmail.com',
            recipients=[user_email]
        )
        msg.body = f"""
        Dear {travel.get('employee', 'Employee')},

        Your travel request has been rejected by {approver_name}.
        Remarks: {remarks}

        Travel Details:
        - Origin: {travel.get('origin', 'Not specified')}
        - Destination: {', '.join(travel.get('destinations', []))}
        - Start Date: {travel.get('startDate')}
        - End Date: {travel.get('endDate')}

        Please check the system for further updates.

        Best regards,
        Travel Authority System
        """
        mail.send(msg)

        return jsonify({'message': f'Travel request rejected by {approver_name}', 'timestamp': timestamp})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cash-advance/<toa_number>/approve', methods=['POST'])
@login_required
def approve_cash_advance(toa_number):
    try:
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        approver_name = user.get('fullName', 'An approver')
        employee_id = user.get('employeeId')

        # Get travel data for reference in notifications
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Update the cash advance approver status
        result = mongo.db.cash_advances.update_one(
            {
                'toaNumber': toa_number,
                'approvers.employeeId': employee_id
            },
            {
                '$set': {
                    'approvers.$.status': 'Approved',
                    'approvers.$.dateApproved': datetime.now().isoformat()
                }
            }
        )

        mongo.db.travels.update_one(
            {
                'toaNumber': toa_number,
                'approvers.employeeId': employee_id
            },
            {
                '$set': {
                    'approvers.$.status': 'Approved',
                    'approvers.$.dateApproved': datetime.now().isoformat()
                }
            }
        )

        # Fetch updated cash advance
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        ca_approvers = cash_advance.get('approvers', [])
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        travel_approvers = travel.get('approvers', [])

        # Find the next pending approver and send email
        next_approver = next((a for a in ca_approvers if a.get('status') == 'Pending'), None)
        if next_approver:
            next_approver_user = mongo.db.users.find_one({'employeeId': next_approver['employeeId']})
            if next_approver_user and 'email' in next_approver_user:
                # Gather details for the email
                ca = cash_advance
                travel_employee = mongo.db.users.find_one({'employeeId': ca.get('employeeId')})
                submitter_name = ca.get('employeeName') or (travel_employee.get('fullName') if travel_employee else 'Employee')
                travel_origin = travel.get('origin', 'Not specified')
                travel_dest = ', '.join(travel.get('destinations', []))
                travel_start = travel.get('startDate')
                travel_end = travel.get('endDate')
                if isinstance(travel_start, datetime):
                    travel_start = travel_start.strftime('%Y-%m-%d')
                if isinstance(travel_end, datetime):
                    travel_end = travel_end.strftime('%Y-%m-%d')
                total_amount = ca.get('totalAmount', 0)
                approval_link = url_for('login', next=url_for('approval_page', toa_number=toa_number), _external=True)

                # Check if travel is international
                if ca.get('isInternational'):
                    def get_float(val, key=None):
                        if isinstance(val, dict) and key:
                            val = val.get(key, 0)
                        try:
                            return float(val)
                        except (TypeError, ValueError):
                            return 0.0

                    meals = ca.get('meals', {})
                    breakfast_usd = get_float(meals.get('breakfast', {}), 'usd')
                    lunch_usd = get_float(meals.get('lunch', {}), 'usd')
                    dinner_usd = get_float(meals.get('dinner', {}), 'usd')
                    total_meals_usd = breakfast_usd + lunch_usd + dinner_usd

                    email_body = f"""Dear {next_approver['name']},

A Travel Order Authority (TOA) and a cash advance request has been submitted for approval by {submitter_name}.

This is an INTERNATIONAL TRAVEL and cash advance.

Travel Details:
- Origin: {travel_origin}
- Destination: {travel_dest}
- Start Date: {travel_start}
- End Date: {travel_end}

Cash Advance Details:
- Total Amount: PHP {total_amount}

Meals:
- Breakfast: USD {breakfast_usd}
- Lunch: USD {lunch_usd}
- Dinner: USD {dinner_usd}
- Total Meals: USD {total_meals_usd}

Daily Allowance:
- USD {ca.get('dailyAllowance', {}).get('usd', 0)}
- {ca.get('dailyAllowance', {}).get('days', 0)} days @ USD 20 per day

Please review and approve/reject it using the following link:
{approval_link}
"""
                else:
                    # Existing domestic email logic
                    meals = ca.get('meals', {})
                    meal_total = meals.get('total', 0)
                    if isinstance(meal_total, dict):
                        meal_total = meal_total.get('php', 0)
                    meal_total = float(meal_total or 0)
                    def get_meal_php(meal):
                        val = meals.get(meal, 0)
                        if isinstance(val, dict):
                            return float(val.get('php', 0))
                        return float(val or 0)
                    breakfast_total = get_meal_php('breakfast')
                    lunch_total = get_meal_php('lunch')
                    dinner_total = get_meal_php('dinner')
                    transportation = ca.get('transportation', 0)
                    details = ca.get('details', '')

                    email_body = f"""Dear {next_approver['name']},

A Travel Order Authority (TOA) and a cash advance request has been submitted for approval by {submitter_name}.

Travel Details:
- Origin: {travel_origin}
- Destination: {travel_dest}
- Start Date: {travel_start}
- End Date: {travel_end}

Cash Advance Details:
- Total Amount: PHP {total_amount}
- Meals Total: PHP {meal_total}
  * Breakfast: PHP {breakfast_total}
  * Lunch: PHP {lunch_total}
  * Dinner: PHP {dinner_total}
- Transportation: PHP {transportation}
"""

                    if details:
                        email_body += f"\nAdditional Details:\n{details}\n"

                    email_body += f"""
Please review and approve/reject it using the following link:
{approval_link}
"""

                msg = Message(
                    subject=f"TOA and Cash Advance Submitted for Approval (TOA #{toa_number})",
                    sender='kubotaphportal@gmail.com',
                    recipients=[next_approver_user['email']]
                )
                msg.body = email_body
                mail.send(msg)

        # Check if all approvers have approved
        all_ca_approved = all(a.get('status') == 'Approved' for a in ca_approvers)
        all_travel_approved = all(a.get('status') == 'Approved' for a in travel_approvers)

        # Get employee info for notifications
        employee_user = mongo.db.users.find_one({'employeeId': cash_advance.get('employeeId')})

        # Send notification about this specific approval
        if employee_user and 'email' in employee_user:
            msg = Message(
                subject=f'Cash Advance Approval Update (TOA #{toa_number})',
                sender='kubotaphportal@gmail.com',
                recipients=[employee_user['email']]
            )

            # Format dates for display
            start_date = travel.get('startDate')
            end_date = travel.get('endDate')
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%B %d, %Y')
            if isinstance(end_date, datetime):
                end_date = end_date.strftime('%B %d, %Y')

            msg.body = f"""
Dear {cash_advance.get('employeeName', 'Employee')},

Your cash advance request for TOA #{toa_number} has been approved by {approver_name}.

Travel Details:
- Origin: {travel.get('origin', 'Not specified')}
- Destination: {', '.join(travel.get('destinations', ['Not specified']))}
- Travel Period: {start_date} to {end_date}
- Total Cash Advance Amount: PHP {cash_advance.get('totalAmount', 0)}

"""
            # Add status information
            if all_ca_approved:
                msg.body += """
Good news! All approvers have now approved your cash advance request.
You will be notified about next steps soon.

"""
            else:
                # Count remaining approvers
                pending_count = sum(1 for a in cash_advance.get('approvers', []) if a.get('status') != 'Approved')
                msg.body += f"""
Your cash advance request still needs approval from {pending_count} more approver(s).
You will be notified when all approvals are complete.

"""
            msg.body += """
Best regards,
Travel Authority System
"""
            mail.send(msg)

        if all_ca_approved:
            # Update overall status
            mongo.db.cash_advances.update_one(
                {'toaNumber': toa_number},
                {'$set': {'status': 'Approved'}}
            )
        if all_travel_approved:
            mongo.db.travels.update_one(
                {'toaNumber': toa_number},
                {'$set': {'approvalStatus': 'Approved'}}
            )

            # Send verification email to Kwell if the travel requires hotel
            if travel.get('requiresHotel', False):
                employee_id = travel.get('employeeId')
                employee_user = mongo.db.users.find_one({'employeeId': employee_id}) if employee_id else None
                division = (employee_user.get('division', '') if employee_user else '').strip()
                coordinator = get_coordinator_for_division(division)
                if coordinator:
                    coordinator_user = mongo.db.users.find_one({'employeeId': coordinator['employeeId']})
                    coordinator_email = coordinator_user['email'] if coordinator_user and 'email' in coordinator_user else None
                else:
                    coordinator_email = None

                if coordinator_email:
                    # Format dates for better readability
                    start_date = travel.get('startDate')
                    end_date = travel.get('endDate')
                    if isinstance(start_date, datetime):
                        start_date = start_date.strftime('%B %d, %Y')
                    if isinstance(end_date, datetime):
                        end_date = end_date.strftime('%B %d, %Y')

                msg = Message(
                    subject=f'Cash Advance Approved - Ready for Verification (TOA #{toa_number})',
                    sender='kubotaphportal@gmail.com',
                    recipients=[coordinator_email]
                )

                verification_link = url_for('login', next=url_for('render_verification_page', toa_number=toa_number), _external=True)

                msg.body = f"""
Dear {coordinator['name']},

The Cash Advance request for TOA #{toa_number} has been fully approved by all approvers and is now ready for verification.

Travel Details:
- Employee: {cash_advance.get('employeeName', 'Not specified')}
- Origin: {travel.get('origin', 'Not specified')}
- Destination: {', '.join(travel.get('destinations', ['Not specified']))}
- Travel Period: {start_date} to {end_date}
- Cash Advance Amount: PHP {cash_advance.get('totalAmount', 0)}

Please proceed with the verification process using the following link:
{verification_link}

Thank you.

Best regards,
Travel Authority System
"""
                mail.send(msg)

            # Notify employee about final approval
            if employee_user and 'email' in employee_user:
                msg = Message(
                    subject=f'Cash Advance FULLY APPROVED (TOA #{toa_number})',
                    sender='kubotaphportal@gmail.com',
                    recipients=[employee_user['email']]
                )

                msg.body = f"""
Dear {cash_advance.get('employeeName', 'Employee')},

Great news! Your cash advance request for TOA #{toa_number} has been FULLY APPROVED by all approvers.

Travel Details:
- Origin: {travel.get('origin', 'Not specified')}
- Destination: {', '.join(travel.get('destinations', ['Not specified']))}
- Travel Period: {start_date} to {end_date}
- Total Cash Advance Amount: PHP {cash_advance.get('totalAmount', 0)}

Safe travels!

Best regards,
Travel Authority System
"""
                mail.send(msg)

        return jsonify({'message': 'Cash advance approved successfully'})

    except Exception as e:
        print(f"Error in approve_cash_advance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cash-advance/<toa_number>/reject', methods=['POST'])
@login_required
def reject_cash_advance(toa_number):
    try:
        data = request.json
        remarks = data.get('remarks', '')

        if not remarks.strip():
            return jsonify({'error': 'Remarks are required for rejection'}), 400

        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        approver_name = user.get('fullName', 'An approver')

        # Get travel data for reference in notifications
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Get the cash advance before updating
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        if not cash_advance:
            return jsonify({'error': 'Cash advance not found'}), 404

        # Update the cash advance approver status
        result = mongo.db.cash_advances.update_one(
            {
                'toaNumber': toa_number,
                'approvers.employeeId': user.get('employeeId')
            },
            {
                '$set': {
                    'approvers.$.status': 'Rejected',
                    'approvers.$.dateApproved': datetime.now().isoformat(),
                    'approvers.$.remarks': remarks
                }
            }
        )
        mongo.db.travels.update_one(
            {
                'toaNumber': toa_number,
                'approvers.employeeId': user.get('employeeId')
            },
            {
                '$set': {
                    'approvers.$.status': 'Rejected',
                    'approvers.$.dateApproved': datetime.now().isoformat(),
                    'approvers.$.remarks': remarks
                }
            }
        )

        # Update the overall status to Rejected
        mongo.db.cash_advances.update_one(
            {'toaNumber': toa_number},
            {'$set': {'status': 'Rejected'}}
        )
        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {'approvalStatus': 'Rejected'}}
        )

        # Get employee info for notifications
        employee_user = mongo.db.users.find_one({'employeeId': cash_advance.get('employeeId')})

        # Send notification to employee about rejection
        if employee_user and 'email' in employee_user:
            # Format dates for display
            start_date = travel.get('startDate')
            end_date = travel.get('endDate')
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%B %d, %Y')
            if isinstance(end_date, datetime):
                end_date = end_date.strftime('%B %d, %Y')

            msg = Message(
                subject=f'Cash Advance Request Rejected (TOA #{toa_number})',
                sender='kubotaphportal@gmail.com',
                recipients=[employee_user['email']]
            )

            msg.body = f"""
Dear {cash_advance.get('employeeName', 'Employee')},

Unfortunately, your cash advance request for TOA #{toa_number} has been rejected by {approver_name}.

Reason for rejection: {remarks}

Travel Details:
- Origin: {travel.get('origin', 'Not specified')}
- Destination: {', '.join(travel.get('destinations', ['Not specified']))}
- Travel Period: {start_date} to {end_date}
- Total Cash Advance Amount: PHP {cash_advance.get('totalAmount', 0)}

You may contact your supervisor or submit a revised cash advance request if needed.

Best regards,
Travel Authority System
"""
            mail.send(msg)

        return jsonify({'message': 'Cash advance rejected successfully'})

    except Exception as e:
        print(f"Error in reject_cash_advance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cash-advance/<toa_number>/send-back', methods=['POST'])
@login_required
def send_back_cash_advance(toa_number):
    try:
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        approver_name = user.get('fullName', 'An approver')
        employee_id = user.get('employeeId')

        # Get cash advance and approvers
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        if not cash_advance:
            return jsonify({'error': 'Cash advance not found'}), 404
        approvers = cash_advance.get('approvers', [])

        # Find the current approver's index
        current_idx = next((i for i, a in enumerate(approvers) if a.get('employeeId') == employee_id and a.get('status') == 'Pending'), None)
        if current_idx is None:
            return jsonify({'error': 'You are not authorized to send back this cash advance.'}), 403

        remarks = request.json.get('remarks', '').strip()
        if not remarks:
            return jsonify({'error': 'Remarks are required for sending back.'}), 400

        # Update approvers' statuses
        for i, a in enumerate(approvers):
            if i == current_idx:
                a['status'] = 'Sent Back'
                a['dateApproved'] = datetime.now().isoformat()
                a['remarks'] = remarks
            else:
                a['status'] = 'Pending'
                a['dateApproved'] = None
                a['remarks'] = ''

        # Set overall status to "Sent Back"
        mongo.db.cash_advances.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'status': 'Sent Back',
                'sentBackRemarks': remarks
            }}
        )
        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'approvalStatus': 'Sent Back',
                'sentBackRemarks': remarks
            }}
        )

        # Notify employee
        employee_id = cash_advance.get('employeeId')
        if not employee_id:
            print("No employeeId in cash_advance")
            return jsonify({'error': 'Cash advance missing employeeId'}), 500
        employee_user = mongo.db.users.find_one({'employeeId': employee_id})
        if employee_user and 'email' in employee_user:
            msg = Message(
                'Cash Advance Sent Back for Revision',
                sender='kubotaphportal@gmail.com',
                recipients=[employee_user['email']]
            )
            msg.body = f"""
Dear {employee_user.get('fullName', 'Employee')},

Your cash advance request for TOA: {toa_number} has been sent back for minor revision.

Remarks from approver:
{remarks}

You may now revise your TOA by clicking the link below:
{url_for('login', next=url_for('edit_toa', toa_number=toa_number), _external=True)}

After updating your TOA, you will be able to proceed to edit your cash advance if needed.

Best regards,
Travel Authority System
"""
            mail.send(msg)
            return jsonify({'message': 'Cash advance sent back to employee for revision.'})

        else:
            return jsonify({'message': 'Cash advance sent back to employee for revision, but no email was sent (employee email not found)'})

    except Exception as e:
        print(f"Error in send_back_cash_advance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/travel/<toa_number>/send-back', methods=['POST'])
@login_required
def send_back_travel(toa_number):
    try:
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        approver_name = user.get('fullName', 'An approver')
        employee_id = user.get('employeeId')

        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404
        approvers = travel.get('approvers', [])

        # Find the current approver's index
        current_idx = next((i for i, a in enumerate(approvers) if a.get('employeeId') == employee_id and a.get('status') == 'Pending'), None)
        if current_idx is None:
            return jsonify({'error': 'You are not authorized to send back this TOA.'}), 403

        remarks = request.json.get('remarks', '').strip()
        if not remarks:
            return jsonify({'error': 'Remarks are required for sending back.'}), 400

        # Update approvers' statuses
        for i, a in enumerate(approvers):
            if i == current_idx:
                a['status'] = 'Sent Back'
                a['dateApproved'] = datetime.now().isoformat()
                a['remarks'] = remarks
            else:
                a['status'] = 'Pending'
                a['dateApproved'] = None
                a['remarks'] = ''

        # Set overall approval status to "Sent Back"
        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'approvalStatus': 'Sent Back',
                'sentBackRemarks': remarks
            }}
        )

        # Notify employee
        travel_user = mongo.db.users.find_one({'employeeId': travel['employeeId']})
        if travel_user and 'email' in travel_user:
            msg = Message(
                'TOA Sent Back for Revision',
                sender='kubotaphportal@gmail.com',
                recipients=[travel_user['email']]
            )
            msg.body = f"""
Dear {travel.get('employee', 'Employee')},

Your travel order (TOA: {toa_number}) has been sent back for minor revision.

Remarks from approver:
{remarks}

You may now revise your TOA by clicking the link below:
{url_for('login', next=url_for('edit_toa_wo_ca', toa_number=toa_number), _external=True)}

Best regards,
Travel Authority System
"""
            mail.send(msg)

        return jsonify({'message': 'TOA sent back to employee for revision.'})

    except Exception as e:
        print(f"Error in send_back_travel: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/edit-cash-advance/<toa_number>', methods=['GET'])
@login_required
def edit_cash_advance(toa_number):
    cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
    if not cash_advance:
        flash('Cash advance not found.', 'danger')
        return redirect(url_for('homepage'))

    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    # Check if user is the owner of this cash advance
    if user.get('employeeId') != cash_advance.get('employeeId'):
        flash('You are not authorized to edit this cash advance.', 'danger')
        return redirect(url_for('home'))

    # Check if cash advance is in "Sent Back" status
    if cash_advance.get('status') != 'Sent Back':
        flash('This cash advance cannot be edited because it has not been sent back for revision.', 'warning')
        return redirect(url_for('home'))

    # Get the travel data for reference
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})

    # Get the remarks from the last approver
    remarks = cash_advance.get('sentBackRemarks', '')

    date_list = []
    if travel and travel.get('startDate') and travel.get('endDate'):
        start = travel['startDate']
        end = travel['endDate']
        if isinstance(start, str):
            start = datetime.strptime(start, '%Y-%m-%d')
        if isinstance(end, str):
            end = datetime.strptime(end, '%Y-%m-%d')
        date_list = [d.strftime('%Y-%m-%d') for d in daterange(start, end)]

    return render_template(
        'edit_cash_advance.html',
        toa_number=toa_number,
        cash_advance=cash_advance,
        travel=travel,
        remarks=remarks,
        user_data=user,
        date_list=date_list
    )

@app.route('/edit-toa/<toa_number>', methods=['GET'])
@login_required
def edit_toa(toa_number):
    # Get the cash advance record for this TOA
    cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
    if not cash_advance:
        flash('Cash advance not found.', 'danger')
        return redirect(url_for('homepage'))

    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    # Check if user is the owner of this TOA
    if user.get('employeeId') != cash_advance.get('employeeId'):
        flash('You are not authorized to edit this TOA.', 'danger')
        return redirect(url_for('homepage'))

    # Check if cash advance is in "Sent Back" status
    if cash_advance.get('status') != 'Sent Back':
        flash('This TOA cannot be edited because the cash advance has not been sent back for revision.', 'warning')
        return redirect(url_for('homepage'))

    # Get the TOA travel data for reference
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('homepage'))

    remarks = cash_advance.get('sentBackRemarks', '')

    return render_template(
        'edit_toa.html',
        toa_number=toa_number,
        travel=travel,
        remarks=remarks,
        user_data=user
    )

@app.route('/api/travel/<toa_number>/update', methods=['POST'])
@login_required
def update_toa(toa_number):
    try:
        data = request.json
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

        # Verify ownership and status
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        if user.get('employeeId') != travel.get('employeeId'):
            return jsonify({'error': 'You are not authorized to edit this TOA'}), 403

        # Check if this TOA has a cash advance
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        if cash_advance:
            # For TOA with cash advance, check status in cash_advances
            if cash_advance.get('status') != 'Sent Back':
                return jsonify({'error': 'This TOA cannot be edited because the cash advance has not been sent back for revision'}), 400
        else:
            # For TOA only, check status in travels
            if travel.get('approvalStatus') != 'Sent Back':
                return jsonify({'error': 'This TOA cannot be edited because it has not been sent back for revision'}), 400

        update_data = {
            'purpose': data.get('purpose', travel.get('purpose')),
            'startDate': datetime.strptime(data.get('startDate'), '%Y-%m-%d') if data.get('startDate') else travel.get('startDate'),
            'endDate': datetime.strptime(data.get('endDate'), '%Y-%m-%d') if data.get('endDate') else travel.get('endDate'),
            'origin': data.get('origin', travel.get('origin')),
            'destinations': data.get('destinations', travel.get('destinations')),
            'remarks': data.get('remarks', travel.get('remarks')),
            'travelMode': data.get('travelMode', travel.get('travelMode')),
            'requiresHotel': data.get('requiresHotel', travel.get('requiresHotel')),
            'itinerary': data.get('itinerary', travel.get('itinerary')),
            'requiresTransportation': data.get('requiresTransportation', travel.get('requiresTransportation')),
            'transportationTypes': data.get('transportationTypes', travel.get('transportationTypes')),
            'carRentalRequested': data.get('carRentalRequested', travel.get('carRentalRequested')),
        }

        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': update_data}
        )

        approvers = travel.get('approvers', [])
        for a in approvers:
            a['status'] = 'Pending'
            a['dateApproved'] = None
            a['remarks'] = ''

        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'status': 'Pending'
            }}
        )

        return jsonify({
            'message': 'TOA updated successfully',
            'redirect': url_for('homepage')
        })

    except Exception as e:
        print(f"Error updating TOA: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cash-advance/<toa_number>/update', methods=['POST'])
@login_required
def update_cash_advance(toa_number):
    try:
        data = request.json
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

        # Verify ownership and status
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        if not cash_advance:
            return jsonify({'error': 'Cash advance not found'}), 404

        if user.get('employeeId') != cash_advance.get('employeeId'):
            return jsonify({'error': 'You are not authorized to edit this cash advance'}), 403

        if cash_advance.get('status') != 'Sent Back':
            return jsonify({'error': 'This cash advance cannot be edited because it has not been sent back for revision'}), 400

        is_international = data.get('isInternational', cash_advance.get('isInternational', False))
        meals = data.get('meals', cash_advance.get('meals', {}))
        detailed = meals.get('detailed', {})

        if is_international:
            breakfast_total_usd = sum(day.get('breakfast', 0) or 0 for day in detailed.values())
            lunch_total_usd = sum(day.get('lunch', 0) or 0 for day in detailed.values())
            dinner_total_usd = sum(day.get('dinner', 0) or 0 for day in detailed.values())
            total_usd = breakfast_total_usd + lunch_total_usd + dinner_total_usd

            meals['breakfast'] = {'usd': breakfast_total_usd}
            meals['lunch'] = {'usd': lunch_total_usd}
            meals['dinner'] = {'usd': dinner_total_usd}
            meals['total'] = {'usd': total_usd}
        else:
            breakfast_total_php = sum(day.get('breakfast', 0) or 0 for day in detailed.values())
            lunch_total_php = sum(day.get('lunch', 0) or 0 for day in detailed.values())
            dinner_total_php = sum(day.get('dinner', 0) or 0 for day in detailed.values())
            total_php = breakfast_total_php + lunch_total_php + dinner_total_php

            meals['breakfast'] = {'php': breakfast_total_php}
            meals['lunch'] = {'php': lunch_total_php}
            meals['dinner'] = {'php': dinner_total_php}
            meals['total'] = {'php': total_php}

        # Update cash advance with new data
        update_data = {
            'meals': meals,
            'dailyAllowance': data.get('dailyAllowance', cash_advance.get('dailyAllowance')),
            'hotel': data.get('hotel', cash_advance.get('hotel', 0)),
            'transportation': data.get('transportation', cash_advance.get('transportation', 0)),
            'transportationPaymentType': data.get('transportationPaymentType', cash_advance.get('transportationPaymentType', '')),
            'tnvsAmount': data.get('tnvsAmount', cash_advance.get('tnvsAmount', 0)),
            'tnvsPaymentType': data.get('tnvsPaymentType', cash_advance.get('tnvsPaymentType', '')),
            'miscellaneous': data.get('miscellaneous', cash_advance.get('miscellaneous', {})),
            'miscTotal': data.get('miscTotal', cash_advance.get('miscTotal', 0)),
            'totalAmount': data.get('totalAmount', cash_advance.get('totalAmount', 0)),
            'details': data.get('details', cash_advance.get('details', '')),
        }

        mongo.db.cash_advances.update_one(
            {'toaNumber': toa_number},
            {'$set': update_data}
        )

        # Reset approval flow: first and last approvers only
        approvers = cash_advance.get('approvers', [])
        for a in approvers:
            a['status'] = 'Pending'
            a['dateApproved'] = None
            a['remarks'] = ''

        # Update in database
        mongo.db.cash_advances.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'status': 'Pending'
            }}
        )

        # Notify first approver
        first_approver = next((a for a in approvers if a['status'] == 'Pending'), None)
        if first_approver:
            approver_user = mongo.db.users.find_one({'employeeId': first_approver['employeeId']})
            if approver_user and 'email' in approver_user:
                approval_link = url_for('login', next=url_for('approval_page', toa_number=toa_number), _external=True)
                msg = Message(
                    'Revised TOA with Cash Advance for Approval',
                    sender='kubotaphportal@gmail.com',
                    recipients=[approver_user['email']]
                )
                msg.body = f"""
Dear {first_approver['name']},

A revised toa with cash advance request has been submitted for approval.
This toa and was previously sent back for revision and has now been updated.

Cash Advance Details:
- TOA Number: {toa_number}
- Employee: {cash_advance.get('employeeName', 'Employee')}
- Total Amount: PHP {update_data['totalAmount']}

Please review and approve/reject it using the following link:
{approval_link}
"""
                mail.send(msg)

        return jsonify({
            'message': 'Cash advance updated successfully',
            'redirect': url_for('homepage')
        })

    except Exception as e:
        print(f"Error updating cash advance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/edit-toa-wo-ca/<toa_number>', methods=['GET'])
@login_required
def edit_toa_wo_ca(toa_number):
    # Get the cash advance record for this TOA
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('homepage'))

    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    # Check if user is the owner of this TOA
    if user.get('employeeId') != travel.get('employeeId'):
        flash('You are not authorized to edit this TOA.', 'danger')
        return redirect(url_for('homepage'))


    if travel.get('approvalStatus') != 'Sent Back':
        flash('This TOA cannot be edited because the travel request has not been sent back for revision.', 'warning')
        return redirect(url_for('homepage'))

    # Get the TOA travel data for reference
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('homepage'))

    remarks = travel.get('sentBackRemarks', '')

    return render_template(
        'edit_toa_wo_ca.html',
        toa_number=toa_number,
        travel=travel,
        remarks=remarks,
        user_data=user
    )

@app.route('/api/travel/<toa_number>/update-wo-ca', methods=['POST'])
@login_required
def update_toa_wo_ca(toa_number):
    try:
        data = request.json
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

        # Verify ownership and status
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        if user.get('employeeId') != travel.get('employeeId'):
            return jsonify({'error': 'You are not authorized to edit this TOA'}), 403

        if travel.get('approvalStatus') != 'Sent Back':
            return jsonify({'error': 'This TOA cannot be edited because it has not been sent back for revision'}), 400

        # ...existing update logic...
        update_data = {
            'purpose': data.get('purpose', travel.get('purpose')),
            'startDate': datetime.strptime(data.get('startDate'), '%Y-%m-%d') if data.get('startDate') else travel.get('startDate'),
            'endDate': datetime.strptime(data.get('endDate'), '%Y-%m-%d') if data.get('endDate') else travel.get('endDate'),
            'origin': data.get('origin', travel.get('origin')),
            'destinations': data.get('destinations', travel.get('destinations')),
            'remarks': data.get('remarks', travel.get('remarks')),
            'travelMode': data.get('travelMode', travel.get('travelMode')),
            'requiresHotel': data.get('requiresHotel', travel.get('requiresHotel')),
            'itinerary': data.get('itinerary', travel.get('itinerary')),
            'requiresTransportation': data.get('requiresTransportation', travel.get('requiresTransportation')),
            'transportationTypes': data.get('transportationTypes', travel.get('transportationTypes')),
            'carRentalRequested': data.get('carRentalRequested', travel.get('carRentalRequested')),
        }

        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': update_data}
        )

        approvers = travel.get('approvers', [])
        for a in approvers:
            a['status'] = 'Pending'
            a['dateApproved'] = None
            a['remarks'] = ''

        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvers': approvers,
                'status': 'Pending'
            }}
        )


        if approvers and len(approvers) > 0:
            first_approver = approvers[0]
            print("First approver:", first_approver)  # Debug
            approver_user = mongo.db.users.find_one({'employeeId': first_approver['employeeId']})
            print("Approver user from DB:", approver_user)  # Debug
            if approver_user and 'email' in approver_user:
                print("Approver email:", approver_user['email'])  # Debug
                approval_link = url_for('login', next=url_for('toa_approval_page', toa_number=toa_number), _external=True)
                msg = Message(
                    'Revised TOA for Approval',
                    sender='kubotaphportal@gmail.com',
                    recipients=[approver_user['email']]
                )
                msg.body = f"""
        Dear {first_approver['name']},

        A revised TOA has been submitted for approval.
        This TOA was previously sent back for revision and has now been updated.

        TOA Details:
        - TOA Number: {toa_number}
        - Employee: {travel.get('employeeName', 'Employee')}

        Please review and approve/reject it using the following link:
        {approval_link}
        """
                try:
                    mail.send(msg)
                    print(f"Email sent to {approver_user['email']}")
                except Exception as e:
                    print(f"Error sending email to {approver_user['email']}: {e}")
            else:
                print("No email found for first approver.")
        else:
            print("No approvers found.")

        return jsonify({
            'message': 'TOA updated successfully',
            'redirect': url_for('homepage')
        })

    except Exception as e:
        print(f"Error updating TOA: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/official-business/<ob_number>/send-back', methods=['POST'])
@login_required
def send_back_ob(ob_number):
    try:
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        employee_id = user.get('employeeId')

        ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
        if not ob:
            return jsonify({'error': 'Official Business request not found'}), 404
        approvers = ob.get('approvers', [])

        # Find the current approver's index
        current_idx = next((i for i, a in enumerate(approvers) if a.get('employeeId') == employee_id and a.get('status') == 'Pending'), None)
        if current_idx is None:
            return jsonify({'error': 'You are not authorized to send back this Official Business.'}), 403

        remarks = request.json.get('remarks', '').strip()
        if not remarks:
            return jsonify({'error': 'Remarks are required for sending back.'}), 400

        # Update approvers' statuses
        for i, a in enumerate(approvers):
            if i == current_idx:
                a['status'] = 'Sent Back'
                a['dateApproved'] = datetime.now().isoformat()
                a['remarks'] = remarks
            else:
                a['status'] = 'Pending'
                a['dateApproved'] = None
                a['remarks'] = ''

        # Set overall status to "Sent Back"
        mongo.db.officialBusinesses.update_one(
            {'obNumber': ob_number},
            {'$set': {
                'approvers': approvers,
                'approvalStatus': 'Sent Back',
                'sentBackRemarks': remarks
            }}
        )

        # Notify employee
        employee_id = ob.get('employeeId')
        employee_user = mongo.db.users.find_one({'employeeId': employee_id})
        if employee_user and 'email' in employee_user:
            msg = Message(
                'Official Business Sent Back for Revision',
                sender='kubotaphportal@gmail.com',
                recipients=[employee_user['email']]
            )
            msg.body = f"""
Dear {employee_user.get('fullName', 'Employee')},

Your Official Business request (OB: {ob_number}) has been sent back for revision.

Remarks from approver:
{remarks}

You may now revise your Official Business by clicking the link below:
{url_for('login', next=url_for('edit_ob', ob_number=ob_number), _external=True)}

Best regards,
Travel Authority System
"""
            mail.send(msg)

        return jsonify({'message': 'Official Business sent back to employee for revision.'})

    except Exception as e:
        print(f"Error in send_back_ob: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/edit-ob/<ob_number>', methods=['GET'])
@login_required
def edit_ob(ob_number):
    ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
    if not ob:
        flash('Official Business request not found.', 'danger')
        return redirect(url_for('homepage'))

    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    if user.get('employeeId') != ob.get('employeeId'):
        flash('You are not authorized to edit this Official Business.', 'danger')
        return redirect(url_for('homepage'))

    if ob.get('approvalStatus') != 'Sent Back':
        flash('This Official Business cannot be edited because it has not been sent back for revision.', 'warning')
        return redirect(url_for('homepage'))

    remarks = ob.get('sentBackRemarks', '')

    return render_template(
        'edit_ob.html',
        ob_number=ob_number,
        ob=ob,
        remarks=remarks,
        user_data=user
    )

@app.route('/api/official-business/<ob_number>/update', methods=['POST'])
@login_required
def update_official_business(ob_number):
    try:
        data = request.json
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

        ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
        if not ob:
            return jsonify({'error': 'Official Business request not found'}), 404

        if user.get('employeeId') != ob.get('employeeId'):
            return jsonify({'error': 'You are not authorized to edit this Official Business'}), 403

        if ob.get('approvalStatus') != 'Sent Back':
            return jsonify({'error': 'This Official Business cannot be edited because it has not been sent back for revision'}), 400

        # Update fields as needed
        update_data = {
            'purpose': data.get('purpose', ob.get('purpose')),
            'startDate': datetime.strptime(data.get('startDate'), '%Y-%m-%d') if data.get('startDate') else ob.get('startDate'),
            'endDate': datetime.strptime(data.get('endDate'), '%Y-%m-%d') if data.get('endDate') else ob.get('endDate'),
            'origin': data.get('origin', ob.get('origin')),
            'destinations': data.get('destinations', ob.get('destinations')),
            'remarks': data.get('remarks', ob.get('remarks')),
            'requiresTransportation': data.get('requiresTransportation', ob.get('requiresTransportation')),
            'transportationTypes': data.get('transportationTypes', ob.get('transportationTypes')),
            'paymentOption': data.get('paymentOption', ob.get('paymentOption')),
        }

        mongo.db.officialBusinesses.update_one(
            {'obNumber': ob_number},
            {'$set': update_data}
        )

        # Reset approval flow: first and last approvers only
        approvers = ob.get('approvers', [])
        for a in approvers:
            a['status'] = 'Pending'
            a['dateApproved'] = None
            a['remarks'] = ''

        mongo.db.officialBusinesses.update_one(
            {'obNumber': ob_number},
            {'$set': {
                'approvers': approvers,
                'status': 'Pending'
            }}
        )

        # Email first approver
        if approvers and len(approvers) > 0:
            first_approver = approvers[0]
            approver_user = mongo.db.users.find_one({'employeeId': first_approver['employeeId']})
            if approver_user and 'email' in approver_user:
                approval_link = url_for('login', next=url_for('ob_approval_page', ob_number=ob_number), _external=True)
                msg = Message(
                    'Revised Official Business for Approval',
                    sender='kubotaphportal@gmail.com',
                    recipients=[approver_user['email']]
                )
                msg.body = f"""
Dear {first_approver['name']},

A revised Official Business request has been submitted for approval.
This request was previously sent back for revision and has now been updated.

OB Details:
- OB Number: {ob_number}
- Employee: {ob.get('employeeName', ob.get('employee', 'Employee'))}

Please review and approve/reject it using the following link:
{approval_link}
"""
                mail.send(msg)

        return jsonify({
            'message': 'Official Business updated successfully',
            'redirect': url_for('homepage')
        })

    except Exception as e:
        print(f"Error updating Official Business: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/cash-advance-release')
@login_required
def cash_advance_release():
    groups = getattr(current_user, 'groups', [])
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'Treasury' not in groups:
        return redirect(url_for('home'))
    return render_template('cash_advance_release.html')

@app.route('/api/cash-advance/list')
@login_required
def api_cash_advance_list():
    groups = getattr(current_user, 'groups', [])
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'Treasury' not in groups:
        return jsonify([]), 403

    # Only return cash advance with ap/dp number
    cash_advances = mongo.db.cash_advances.find({'apdpNumber': {'$exists': True, '$ne': ''}})

    return jsonify([
        {
            'toa_number': ca.get('toaNumber', ca.get('toa_number')),
            'employeeName': ca.get('employeeName', ca.get('employee')),
            'requestDate': ca.get('requestDate', ''),
            'status': ca.get('status', ''),
            'totalAmount': ca.get('totalAmount', 0),
            'travelType': ca.get('travelType', ''),
            'isInternational': ca.get('isInternational', False),
            'released': ca.get('released', False),
            'releaseDate': ca.get('releaseDate', ''),
            'apdpNumber': ca.get('apdpNumber', '')
        } for ca in cash_advances
    ])

@app.route('/api/cash-advance/<toa_number>')
@login_required
def api_cash_advance_detail(toa_number):
    ca = mongo.db.cash_advances.find_one({'$or': [{'toaNumber': toa_number}, {'toa_number': toa_number}]})
    if not ca:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'employeeName': ca.get('employeeName', ca.get('employee')),
        'requestDate': ca.get('requestDate', ''),
        'totalAmount': ca.get('totalAmount', 0),
        'status': ca.get('status', ''),
        'details': ca.get('details', ''),
        'approvers': ca.get('approvers', []),
        'sentBackRemarks': ca.get('sentBackRemarks', ''),
        'isInternational': ca.get('isInternational', False),
        'travelType': ca.get('travelType', ''),
        'released': ca.get('released', False),
        'releaseDate': ca.get('releaseDate', ''),
    })

@app.route('/api/cash-advance/<toa_number>/release', methods=['POST'])
@login_required
def api_cash_advance_release(toa_number):
    groups = getattr(current_user, 'groups', [])
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'Treasury' not in groups:
        return jsonify({'error': 'Access denied'}), 403

    ca = mongo.db.cash_advances.find_one({'$or': [{'toaNumber': toa_number}, {'toa_number': toa_number}]})
    if not ca:
        return jsonify({'error': 'Not found'}), 404

    if ca.get('released', False):
        return jsonify({'error': 'Cash advance already released'}), 400

    employee_id = ca.get('employeeId')
    if not employee_id:
        return jsonify({'error': 'Employee ID not found in cash advance record.'}), 500

    employee_user = mongo.db.users.find_one({'employeeId': employee_id})
    employee_email = employee_user.get('email') if employee_user else None
    if not employee_email:
        return jsonify({'error': 'Employee email not found.'}), 500

    try:
        total_amount = float(ca.get('totalAmount', 0))
        verification = mongo.db.verifications.find_one({'toaNumber': toa_number})
        hotel_amount = 0
        if verification and verification.get('hotel', {}).get('paymentType') == 'Cash':
            try:
                hotel_amount = float(verification['hotel'].get('amount', 0))
            except Exception:
                hotel_amount = 0
            total_amount += hotel_amount

        msg = Message(
            subject='Your Cash Advance is Ready for Release',
            sender='kubotaphportal@gmail.com',
            recipients=[employee_email]
        )

        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        currency = 'USD' if (travel and travel.get('isInternational')) else 'PHP'

        msg.body = f"""Dear {ca.get('employeeName', 'Employee')},

Your cash advance for TOA {toa_number} is now ready for release.

Cash Advance Details:
- TOA Number: {toa_number}
- Amount: {currency} {total_amount:,.2f}"""

        if hotel_amount > 0:
            msg.body += f"\n  (Includes hotel payment in cash: {currency} {hotel_amount:,.2f})"

        msg.body += """

Kindly expect the amount of Cash Advance to your pay card.

Best regards,
Treasury Department
Travel Authority System
"""
        mail.send(msg)

        mongo.db.cash_advances.update_one(
            {'$or': [{'toaNumber': toa_number}, {'toa_number': toa_number}]},
            {'$set': {
                'released': True,
                'releaseDate': datetime.now().isoformat(),
                'releasedBy': current_user.employee_id
            }}
        )

        return jsonify({'message': 'Release email sent to employee and cash advance marked as released.'})

    except Exception as e:
        print(f"Error releasing cash advance: {str(e)}")
        return jsonify({'error': 'Failed to send release notification'}), 500

@app.route('/api/verification/<toa_number>', methods=['GET', 'POST'])
@login_required
def verification_page(toa_number):
    if request.method == 'GET':
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({"error": "Travel not found"}), 404

        verification = mongo.db.verifications.find_one({'toaNumber': toa_number})
        if not verification:
            return jsonify({
                'toaNumber': toa_number,
                'flightDetails': {'departure': '', 'arrival': ''},
                'hotels': [],
                'verifiedBy': '',
                'verificationStatus': 'Pending',
                'remarks': ''
            })
        verification['_id'] = str(verification['_id'])
        # Ensure hotels is always a list
        if 'hotels' not in verification and 'hotel' in verification:
            verification['hotels'] = [verification['hotel']]
        return jsonify(verification)

    if request.method == 'POST':
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
        employee_id = travel.get('employeeId')
        employee_user = mongo.db.users.find_one({'employeeId': employee_id}) if employee_id else None
        division = (employee_user.get('division', '') if employee_user else '').strip()
        coordinator = get_coordinator_for_division(division)
        if not user or user.get('employeeId') != (coordinator['employeeId'] if coordinator else None):
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.json
        required_fields = ['flightDetails', 'hotels', 'verificationStatus']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        mongo.db.verifications.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'flightDetails': data['flightDetails'],
                'hotels': data['hotels'],
                'verifiedBy': user.get('employeeId', ''),
                'verifierName': user.get('fullName', ''),
                'verificationStatus': data['verificationStatus'],
                'remarks': data.get('remarks', ''),
                'verificationDate': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            }},
            upsert=True
        )

        # Email logic (send details for all hotels)
        if travel:
            employee_id = travel.get('employeeId')
            employee_name = travel.get('employee', 'Employee')
            employee_user = mongo.db.users.find_one({'employeeId': employee_id})
            if employee_user and 'email' in employee_user:
                employee_email = employee_user['email']
                departure_time = "Not specified"
                arrival_time = "Not specified"

                def format_datetime_for_email(dt_str):
                    try:
                        if not dt_str:
                            return "Not specified"
                        if 'T' in dt_str:
                            if dt_str.endswith('Z'):
                                dt_str = dt_str[:-1] + '+00:00'
                            elif '+' not in dt_str and ':' not in dt_str[-6:]:
                                dt_str += '+00:00'
                        dt = datetime.fromisoformat(dt_str)
                        return dt.strftime('%B %d, %Y %I:%M %p')
                    except Exception:
                        return str(dt_str)

                if data['flightDetails']['departure']:
                    departure_time = format_datetime_for_email(data['flightDetails']['departure'])
                if data['flightDetails']['arrival']:
                    arrival_time = format_datetime_for_email(data['flightDetails']['arrival'])

                hotel_details = ""
                for idx, hotel in enumerate(data['hotels'], 1):
                    hotel_details += f"""
Hotel {idx}:
- Location: {hotel.get('location', 'Not specified')}
- Hotel Name: {hotel.get('name', 'Not specified')}
- Start Date: {hotel.get('startDate', 'Not specified')}
- End Date: {hotel.get('endDate', 'Not specified')}
- Amount: {hotel.get('amount', 'Not specified')}
- Payment Method: {hotel.get('paymentType', 'Not specified')}
"""

                msg = Message(
                    subject=f'Your Travel Order (TOA: {toa_number}) has been verified',
                    sender='kubotaphportal@gmail.com',
                    recipients=[employee_email]
                )
                report_link = url_for('login', next=url_for('toa_final_report', toa_number=toa_number), _external=True)
                msg.body = f"""
Dear {employee_name},

Your travel order (TOA: {toa_number}) has been verified by {user.get('fullName', 'the coordinator')} and is now complete.

Verification Details:

Flight Information:
- Departure: {departure_time}
- Return: {arrival_time}

Hotel Details:
{hotel_details}

Remarks:
{data.get('remarks', 'None')}

You can view and print your final report here (login required):
{report_link}

For any questions or concerns, please contact the travel coordinator.

Best regards,
Travel Authority System
"""
                mail.send(msg)

        return jsonify({'message': 'Verification details saved successfully and email notification sent'})


@app.route('/cash-advance-monitor')
@login_required
def cash_advance_monitor():
    groups = getattr(current_user, 'groups', [])
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'General Accounting' not in groups:
        flash('Access denied. Only General Accounting employees can view this page.', 'danger')
        return redirect(url_for('home'))
    return render_template('cash_advance_monitor.html')

@app.route('/api/cash-advance/<toa_number>/apdp', methods=['POST'])
@login_required
def set_apdp_number(toa_number):
    groups = getattr(current_user, 'groups', []) #to check if the user is under General Accounting group
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'General Accounting' not in groups:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    apdp_number = data.get('apdpNumber', '').strip()
    mongo.db.cash_advances.update_one(
        {'$or': [{'toaNumber': toa_number}, {'toa_number': toa_number}]},
        {'$set': {'apdpNumber': apdp_number}}
    )

    treasury_users = list(mongo.db.users.find({'section': {'$in': ['Treasury']}, 'email': {'$exists': True, '$ne': ''}}))
    cash_advance = mongo.db.cash_advances.find_one({'$or': [{'toaNumber': toa_number}, {'toa_number': toa_number}]})
    employee_name = cash_advance.get('employeeName', cash_advance.get('employee', ''))
    employee_email = cash_advance.get('employeeEmail')

    if not employee_email:
        employee_id = cash_advance.get('employeeId')
        employee_user = mongo.db.users.find_one({'employeeId': employee_id})
        employee_email = employee_user.get('email') if employee_user else None

    subject = f"Cash Advance Ready for Release: TOA {toa_number}"
    body = f"""
Dear Treasury Team,

A cash advance for TOA Number {toa_number} ({employee_name}) now has an AP/DP Number: {apdp_number}.

Please proceed with the release process.

Best regards,
Travel Authority System
"""
    for user in treasury_users:
        msg = Message(subject, sender='kubotaphportal@gmail.com', recipients=[user['email']])
        msg.body = body
        mail.send(msg)

    if employee_email:
        emp_subject = f"Your Cash Advance AP/DP Number for TOA {toa_number}"
        emp_body = f"""
Dear {employee_name},

Your cash advance for TOA Number {toa_number} has been assigned AP/DP Number: {apdp_number}.

You will be notified once your cash advance is released.

Best regards,
Travel Authority System
"""
        emp_msg = Message(emp_subject, sender='kubotaphportal@gmail.com', recipients=[employee_email])
        emp_msg.body = emp_body
        mail.send(emp_msg)

    return jsonify({'message': 'AP/DP Number saved, Treasury and employee notified.'})

@app.route('/api/cash-advance/all')
@login_required
def api_cash_advance_all():
    groups = getattr(current_user, 'groups', [])
    if not isinstance(groups, list):
        groups = [groups] if groups else []
    if 'General Accounting' not in groups:
        return jsonify([]), 403

    cash_advances = list(mongo.db.cash_advances.find())
    return jsonify([
        {
            'toa_number': ca.get('toaNumber', ca.get('toa_number')),
            'employeeName': ca.get('employeeName', ca.get('employee')),
            'requestDate': ca.get('requestDate', ''),
            'status': ca.get('status', ''),
            'totalAmount': ca.get('totalAmount', 0),
            'travelType': ca.get('travelType', ''),
            'isInternational': ca.get('isInternational', False),
            'released': ca.get('released', False),
            'releaseDate': ca.get('releaseDate', ''),
            'apdpNumber': ca.get('apdpNumber', '')
        } for ca in cash_advances
    ])

@app.route('/api/cash-advance/<toa_number>', methods=['GET'])
@login_required
def get_cash_advance(toa_number):
    cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
    if not cash_advance:
        return jsonify({'error': 'Cash advance not found'}), 404

    verification = mongo.db.verifications.find_one({'toaNumber': toa_number})
    if verification and 'hotel' in verification:
        cash_advance['hotelVerification'] = verification['hotel']
    else:
        cash_advance['hotelVerification'] = None

    return jsonify({
        'approvers': cash_advance.get('approvers', []),
    })

@app.route('/car-rental-approval/<toa_number>', methods=['GET', 'POST'])
@login_required
def car_rental_approval(toa_number):
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel or not travel.get('carRentalRequested'):
        return "Car rental request not found.", 404

    if request.method == 'POST':
        action = request.form.get('action')
        remarks = request.form.get('remarks', '')
        payment_type = request.form.get('paymentType')
        amount = request.form.get('amount') if payment_type == 'Cash' else None

        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'carRentalApproval': {
                    'status': 'Approved' if action == 'approve' else 'Rejected',
                    'remarks': remarks,
                    'paymentType': payment_type,
                    'amount': float(amount) if amount else None,
                    'date': datetime.now()
                }
            }}
        )
        return render_template('car_rental_approval_result.html', status=action, remarks=remarks)

    return render_template('car_rental_approval.html', travel=travel)

@app.route('/cash-advance/<toa_number>', methods=['GET'])
@login_required
def render_cash_advance_form(toa_number):
    # Just check if the TOA exists and the user is the owner
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('Travel request not found.', 'danger')
        return redirect(url_for('home'))

    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    if user.get('employeeId') != travel.get('employeeId'):
        flash('You are not authorized to request a cash advance for this TOA.', 'danger')
        return redirect(url_for('home'))

    # Dates for display
    toa_date = travel.get('dateFiled')
    if isinstance(toa_date, datetime):
        toa_date = toa_date.strftime('%B %d, %Y')
    elif isinstance(toa_date, str):
        try:
            toa_date = datetime.fromisoformat(toa_date.replace('Z', '+00:00')).strftime('%B %d, %Y')
        except:
            toa_date = 'Not specified'
    else:
        toa_date = 'Not specified'

    today_date = datetime.now().strftime('%B %d, %Y')

    approvers = get_dynamic_approvers(travel['employeeId'])
    formatted_approvers = []
    for approver in approvers:
        formatted_approvers.append({
            'employeeId': approver['employeeId'],
            'name': approver['name'],
            'position': approver['position'],
            'status': 'Pending',
            'dateApproved': None
        })

    return render_template(
        'cash_advance.html',
        toa_number=toa_number,
        employee_name=travel.get('employee', 'Not specified'),
        toa_date=toa_date,
        today_date=today_date,
        hotel_amount=0,
        approvers=formatted_approvers,
        travel=travel
    )

@app.route('/api/cash-advance/<toa_number>', methods=['POST'])
@login_required
def submit_cash_advance(toa_number):
    try:
        # Get the current user
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

        # Verify that the TOA exists and has been approved
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})

        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Check if the user is the employee associated with this TOA
        if user.get('employeeId') != travel.get('employeeId'):
            return jsonify({'error': 'You are not authorized to request a cash advance for this TOA'}), 403

        # Get the submitted data
        data = request.json

        is_international = data.get('isInternational', travel.get('isInternational', False))

        # Create a new cash advance request
        approvers = get_dynamic_approvers(travel['employeeId'], is_international=is_international)
        formatted_approvers = []
        for approver in approvers:
            formatted_approvers.append({
                'employeeId': approver['employeeId'],
                'name': approver['name'],
                'position': approver['position'],
                'status': 'Pending',
                'dateApproved': None
            })

        cash_advance = {
            'toaNumber': toa_number,
            'employeeId': user.get('employeeId'),
            'employeeName': data.get('employeeName'),
            'requestDate': datetime.now().isoformat(),
            'isInternational': data.get('isInternational', False),
            'exchangeRate': data.get('exchangeRate', 1),
            'meals': data.get('meals', {}),
            'dailyAllowance': data.get('dailyAllowance'),
            'hotel': data.get('hotel', 0),
            'transportation': data.get('transportation', 0),
            'transportationPaymentType': data.get('transportationPaymentType', ''),
            'tnvsAmount': data.get('tnvsAmount', 0),
            'tnvsPaymentType': data.get('tnvsPaymentType', ''),
            'miscellaneous': data.get('miscellaneous', {}),
            'miscTotal': data.get('miscTotal', 0),
            'totalAmount': data.get('totalAmount', 0),
            'details': data.get('details', ''),
            'approvers': formatted_approvers,
            'status': 'Pending'
        }

        # Save to database
        result = mongo.db.cash_advances.insert_one(cash_advance)

        # Format the meal details
        meals = data.get('meals', {})
        meal_total = meals.get('total', 0)
        if isinstance(meal_total, dict):
            meal_total = meal_total.get('php', 0)
        meal_total = float(meal_total or 0)

        def get_meal_php(meal):
            val = meals.get(meal, 0)
            if isinstance(val, dict):
                return float(val.get('php', 0))
            return float(val or 0)

        breakfast_total = get_meal_php('breakfast')
        lunch_total = get_meal_php('lunch')
        dinner_total = get_meal_php('dinner')

        # Format miscellaneous expenses
        misc_items = []
        misc_expenses = data.get('miscellaneous', {})
        for expense_type, expense_data in misc_expenses.items():
            misc_items.append(f"  * {expense_data.get('label', 'Unknown')}: PHP {expense_data.get('amount', 0)}")

        misc_details = "\n".join(misc_items) if misc_items else "  * None"

        # Send email only to the first approver
        if approvers:
            approver = approvers[0]
            try:
                subject = f"TOA and Cash Advance Submitted for Approval (TOA #{toa_number})"
                approval_link = url_for('login', next=url_for('approval_page', toa_number=toa_number), _external=True)

                # Build the email body based on whether it's international or not
                if data.get('isInternational'):
                    def get_float(val, key=None):
                        if isinstance(val, dict) and key:
                            val = val.get(key, 0)
                        try:
                            return float(val)
                        except (TypeError, ValueError):
                            return 0.0
                    breakfast_usd = get_float(data.get('meals', {}).get('breakfast', {}), 'usd')
                    lunch_usd = get_float(data.get('meals', {}).get('lunch', {}), 'usd')
                    dinner_usd = get_float(data.get('meals', {}).get('dinner', {}), 'usd')
                    total_meals_usd = breakfast_usd + lunch_usd + dinner_usd

                    email_body = f"""
Dear {approver['name']},

A Travel Order Authority (TOA) and a cash advance request has been submitted for approval by {data.get('employeeName')}.

This is an INTERNATIONAL TRAVEL and cash advance.

Travel Details:
- Origin: {travel['origin']}
- Destination: {', '.join(travel['destinations'])}
- Start Date: {travel['startDate'].strftime('%Y-%m-%d') if isinstance(travel['startDate'], datetime) else travel['startDate']}
- End Date: {travel['endDate'].strftime('%Y-%m-%d') if isinstance(travel['endDate'], datetime) else travel['endDate']}

Cash Advance Details:
- Total Amount: PHP {data.get('totalAmount', 0)}

Meals:
- Breakfast: USD {breakfast_usd}
- Lunch: USD {lunch_usd}
- Dinner: USD {dinner_usd}
- Total Meals: USD {total_meals_usd}

Daily Allowance:
- USD {data.get('dailyAllowance', {}).get('usd', 0)}
- {data.get('dailyAllowance', {}).get('days', 0)} days @ USD 20 per day

Please review and approve/reject it using the following link:
{approval_link}
"""
                else:
                    email_body = f"""
Dear {approver['name']},

A Travel Order Authority (TOA) and a cash advance request has been submitted for approval by {data.get('employeeName')}.

Travel Details:
- Origin: {travel['origin']}
- Destination: {', '.join(travel['destinations'])}
- Start Date: {travel['startDate'].strftime('%Y-%m-%d') if isinstance(travel['startDate'], datetime) else travel['startDate']}
- End Date: {travel['endDate'].strftime('%Y-%m-%d') if isinstance(travel['endDate'], datetime) else travel['endDate']}

Cash Advance Details:
- Total Amount: PHP {data.get('totalAmount', 0)}
- Meals Total: PHP {meal_total}
  * Breakfast: PHP {breakfast_total}
  * Lunch: PHP {lunch_total}
  * Dinner: PHP {dinner_total}
"""

                    if data.get('hotel', 0) > 0:
                        email_body += f"- Hotel: PHP {data.get('hotel', 0)}\n"
                    if data.get('tnvsPaymentType', '').lower() == 'cash':
                        email_body += f"- Transportation (TNVS): PHP {data.get('tnvsAmount', 0)}\n"
                    elif data.get('transportation', 0) > 0:
                        email_body += f"- Transportation: PHP {data.get('transportation', 0)}\n"
                    if misc_items:
                        email_body += f"- Miscellaneous Expenses (PHP {data.get('miscTotal', 0)}):\n{misc_details}\n"
                    if data.get('details'):
                        email_body += f"\nAdditional Details:\n{data.get('details')}\n"
                    email_body += f"\nPlease review and approve/reject it using the following link:\n{approval_link}"

                msg = Message(
                    subject=f"TOA and Cash Advance Submitted for Approval (TOA #{toa_number})",
                    sender='kubotaphportal@gmail.com',
                    recipients=[approver['email']]
                )
                msg.body = email_body
                mail.send(msg)
            except Exception as e:
                print(f"Error sending email to approver {approver['name']}: {str(e)}")

        # Send confirmation email to employee
        try:
            employee_user = mongo.db.users.find_one({'employeeId': user.get('employeeId')})
            if employee_user and 'email' in employee_user:
                meal_details = []
                meal_details_by_date = data.get('meals', {}).get('detailed', {})

                if meal_details_by_date:
                    meal_details.append("Meals by Date:")
                    for date_str, meals in meal_details_by_date.items():
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%B %d, %Y')
                        except:
                            formatted_date = date_str

                        date_meals = []
                        for meal_type in ['breakfast', 'lunch', 'dinner']:
                            meal_val = meals.get(meal_type, 0)
                            if meal_val and ((isinstance(meal_val, dict) and (meal_val.get('php', 0) > 0 or meal_val.get('usd', 0) > 0)) or (isinstance(meal_val, (int, float, str)) and float(meal_val) > 0)):
                                date_meals.append(meal_type.capitalize())

                        if date_meals:
                            def safe_float(val, key):
                                if isinstance(val, dict):
                                    val = val.get(key, 0)
                                try:
                                    return float(val)
                                except (TypeError, ValueError):
                                    return 0.0

                            if data.get('isInternational'):
                                total_usd = sum(safe_float(v, 'usd') for v in meals.values())
                                total_php = sum(safe_float(v, 'php') for v in meals.values())
                                meal_details.append(f"  * {formatted_date}: {', '.join(date_meals)} (USD {total_usd})")
                            else:
                                total_php = sum(safe_float(v, 'php') if isinstance(v, dict) else safe_float(v, None) for v in meals.values())
                                meal_details.append(f"  * {formatted_date}: {', '.join(date_meals)} (PHP {total_php})")

                meal_details_text = "\n".join(meal_details) if meal_details else "  * None"

                email_body = f"""
Dear {data.get('employeeName')},

Your cash advance request for TOA: {toa_number} has been submitted successfully.

Cash Advance Details:
- Total Amount: PHP {data.get('totalAmount', 0)}
"""

                if data.get('isInternational'):
                    meals = data.get('meals', {})
                    breakfast_usd = float(meals.get('breakfast', {}).get('usd', 0))
                    lunch_usd = float(meals.get('lunch', {}).get('usd', 0))
                    dinner_usd = float(meals.get('dinner', {}).get('usd', 0))
                    daily_allowance_usd = float(data.get('dailyAllowance', {}).get('usd', 0))
                    daily_allowance_days = data.get('dailyAllowance', {}).get('days', 0)

                    total_usd = (
                        breakfast_usd +
                        lunch_usd +
                        dinner_usd +
                        daily_allowance_usd
                    )

                    email_body += f"- Total Amount (USD): {total_usd:.2f}\n"
                    email_body += f"- Daily Allowance: USD {daily_allowance_usd} for {daily_allowance_days} day(s)\n"

                if meal_details_text:
                    email_body += f"{meal_details_text}\n"
                if data.get('hotel', 0) > 0:
                    email_body += f"- Hotel: PHP {data.get('hotel', 0)}\n"
                if data.get('tnvsPaymentType', '').lower() == 'cash':
                    email_body += f"- Transportation (TNVS): PHP {data.get('tnvsAmount', 0)}\n"
                elif data.get('transportation', 0) > 0:
                    email_body += f"- Transportation: PHP {data.get('transportation', 0)}\n"
                if misc_items:
                    email_body += f"- Miscellaneous Expenses (PHP {data.get('miscTotal', 0)}):\n{misc_details}\n"
                if data.get('details'):
                    email_body += f"\nAdditional Details:\n{data.get('details')}\n"

                email_body += """
Your request is pending approval from the approvers. You will be notified once it is approved.

Best regards,
Travel Authority System
"""
                msg = Message(
                    subject=f'Cash Advance Request Submitted for TOA: {toa_number}',
                    sender='kubotaphportal@gmail.com',
                    recipients=[employee_user['email']]
                )
                msg.body = email_body
                mail.send(msg)
        except Exception as e:
            print(f"Error sending email to employee: {str(e)}")

        return jsonify({
            'message': 'Cash advance request submitted successfully',
            'id': str(result.inserted_id)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/travel/<toa_number>/flight-schedule', methods=['POST'])
@login_required
def update_flight_schedule(toa_number):
    try:
        # Get the travel request
        travel = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not travel:
            return jsonify({'error': 'Travel request not found'}), 404

        # Get the employee's division
        employee_id = travel.get('employeeId')
        employee_user = mongo.db.users.find_one({'employeeId': employee_id}) if employee_id else None
        division = (employee_user.get('division', '') if employee_user else '').strip()
        coordinator = get_coordinator_for_division(division)

        # Check if current user is the coordinator for this division
        user = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
        if not coordinator or user.get('employeeId') != coordinator['employeeId']:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        def parse_date(dt_str):
            if not dt_str:
                return None
            try:
                # Handle both with and without timezone
                if 'T' in dt_str:
                    if dt_str.endswith('Z'):
                        dt_str = dt_str[:-1] + '+00:00'
                    elif '+' not in dt_str and ':' not in dt_str[-6:]:
                        dt_str += '+00:00'
                return datetime.fromisoformat(dt_str)
            except ValueError:
                raise ValueError(f"Invalid datetime format: {dt_str}")

        # Validate and parse datetimes
        departure = None
        arrival = None

        if data.get('departure'):
            try:
                departure = datetime.fromisoformat(data['departure'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid departure datetime format'}), 400

        if data.get('arrival'):
            try:
                arrival = datetime.fromisoformat(data['arrival'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid arrival datetime format'}), 400

        # Update database
        result = mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {'flightSchedule': {
                'departure': departure,
                'arrival': arrival
            }}}
        )

        return jsonify({
            'message': 'Flight schedule updated successfully',
            'modified_count': result.modified_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/toa-final-report/<toa_number>')
@login_required
def toa_final_report(toa_number):
    # Fetch TOA data
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('TOA not found.', 'danger')
        return redirect(url_for('home'))

    # Fetch cash advance data (if any)
    cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})

    # Fetch verification data (if any)
    verification = mongo.db.verifications.find_one({'toaNumber': toa_number})

    return render_template(
        'toa_final_report.html',
        travel_data=travel,
        cash_advance=cash_advance,
        verification=verification
    )

@app.route('/toa-report/<toa_number>')
@login_required
def toa_report(toa_number):
    # Fetch TOA data
    travel = mongo.db.travels.find_one({'toaNumber': toa_number})
    if not travel:
        flash('TOA not found.', 'danger')
        return redirect(url_for('home'))

    return render_template(
        'toa_report.html',
        travel_data=travel
    )

@app.route('/ob-report/<ob_number>')
@login_required
def ob_final_report(ob_number):
    # Fetch OB data
    ob = mongo.db.officialBusinesses.find_one({'obNumber': ob_number})
    if not ob:
        flash('Official Business not found.', 'danger')
        return redirect(url_for('home'))

    # Fetch cash advance data (if any)
    cash_advance = mongo.db.ob_cash_advances.find_one({'obNumber': ob_number})

    # OBs typically do not have verification, but you can add if needed
    return render_template(
        'ob_final_report.html',
        ob_data=ob,
        cash_advance=cash_advance
    )

@app.route('/api/travel/<toa_number>/status', methods=['GET'])
def get_approval_status(toa_number):
    travel = mongo.db.travels.find_one({'toaNumber': toa_number}, {'approvers': 1})
    if not travel:
        return jsonify({'error': 'Travel request not found'}), 404
    return jsonify({'approvers': travel['approvers']})

@app.route('/api/travel/<toa_number>', methods=['PUT'])
def update_travel(toa_number):
    data = request.json
    approvers = get_dynamic_approvers(data['employeeId'])
    updated_travel = {
        'toaNumber': data['toaNumber'],
        'dateFiled': datetime.strptime(data['dateFiled'], '%Y-%m-%d %H:%M'),
        'travelType': data['travelType'],
        'employeeId': data['employeeId'],
        'employee': data['employee'],
        'department': data['department'],
        'position': data['position'],
        'startDate': datetime.strptime(data['startDate'], '%Y-%m-%d'),
        'endDate': datetime.strptime(data['endDate'], '%Y-%m-%d'),
        'origin': data['origin'],
        'destinations': data['destinations'],
        'purpose': data['purpose'],
        'approvalStatus': data['approvalStatus'],
        'remarks': data['remarks'],
        'itinerary': data.get('itinerary', []),  # Add itinerary data
        'approvers': [
                {
                    'name': a['name'],
                    'employeeId': a['employeeId'],
                    'position': a['position'],
                    'status': 'Pending',
                    'dateApproved': None
                } for a in approvers
            ]
    }
    mongo.db.travels.update_one({'toaNumber': toa_number}, {'$set': updated_travel})
    return jsonify({'message': 'Travel request updated'})

@app.route('/cancel-toa')
@login_required
def cancel_toa_page():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    # Check if user is a coordinator
    user_employee_id = user.get('employeeId')
    is_coordinator = False
    coordinator_division = None

    # Check against all division coordinators
    coordinators = {
        'AMC052024-457': 'Sales & Marketing',
        'LOU070124-460': 'Customer Solutions',
        'KSMZ022122-367': 'Finance, ICT & Admin',
        'MDMA120102-094': 'Davao Branch'
    }

    if user_employee_id in coordinators:
        is_coordinator = True
        coordinator_division = coordinators[user_employee_id]

    if not is_coordinator:
        flash('Access denied. Only coordinators can access this page.', 'danger')
        return redirect(url_for('homepage'))

    return render_template('cancel_toa.html', coordinator_division=coordinator_division)

@app.route('/api/toa/by-division/<division>')
@login_required
def get_toa_by_division(division):
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    user_employee_id = user.get('employeeId')

    import urllib.parse
    division = urllib.parse.unquote(division)

    print(f"=== DEBUG INFO ===")
    print(f"Received division: '{division}'")
    print(f"User employee ID: '{user_employee_id}'")
    print(f"User data: {user}")

    # Verify coordinator access
    coordinators = {
        'AMC052024-457': 'Sales & Marketing',
        'LOU070124-460': 'Customer Solutions',
        'KSMZ022122-367': 'Finance, ICT & Admin',
        'MDMA120102-094': 'Davao Branch'
    }

    print(f"Coordinators mapping: {coordinators}")
    print(f"Expected division for user: {coordinators.get(user_employee_id)}")

    if user_employee_id not in coordinators:
        return jsonify({'error': f'User {user_employee_id} is not a coordinator'}), 403

    if coordinators[user_employee_id] != division:
        return jsonify({'error': f'Access denied. User division: {coordinators[user_employee_id]}, requested: {division}'}), 403

    try:
        # Get all employees from the division
        if division == 'Finance, ICT & Admin':
            # Handle multiple division names for Finance
            division_employees = list(mongo.db.users.find({
                'division': {'$in': ['Finance', 'ICT & Admin', 'Finance, ICT & Admin']}
            }, {'employeeId': 1}))
        else:
            division_employees = list(mongo.db.users.find({
                'division': division
            }, {'employeeId': 1}))

        employee_ids = [emp['employeeId'] for emp in division_employees]

        # Get TOAs for these employees (exclude cancelled ones)
        toas = list(mongo.db.travels.find({
            'employeeId': {'$in': employee_ids},
            'approvalStatus': {'$ne': 'Cancelled'}
        }).sort('dateFiled', -1))

        # Format the response
        result = []
        for toa in toas:
            # Get employee details
            employee = mongo.db.users.find_one({'employeeId': toa.get('employeeId')})

            # Get cash advance status if exists
            cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa.get('toaNumber')})

            result.append({
                'toaNumber': toa.get('toaNumber'),
                'employee': toa.get('employee'),
                'employeeId': toa.get('employeeId'),
                'division': employee.get('division') if employee else 'Unknown',
                'department': employee.get('department') if employee else 'Unknown',
                'dateFiled': toa.get('dateFiled').isoformat() if toa.get('dateFiled') else '',
                'startDate': toa.get('startDate').isoformat() if toa.get('startDate') else '',
                'endDate': toa.get('endDate').isoformat() if toa.get('endDate') else '',
                'destinations': toa.get('destinations', []),
                'purpose': toa.get('purpose', ''),
                'approvalStatus': toa.get('approvalStatus', 'Pending'),
                'isInternational': toa.get('isInternational', False),
                'hasCashAdvance': cash_advance is not None,
                'cashAdvanceStatus': cash_advance.get('status') if cash_advance else None
            })

        return jsonify(result)

    except Exception as e:
        print(f"Error in get_toa_by_division: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toa/<toa_number>/cancel', methods=['POST'])
@login_required
def cancel_toa(toa_number):
    try:
        user_id = current_user.id
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        user_employee_id = user.get('employeeId')

        # Verify coordinator access
        coordinators = {
            'AMC052024-457': 'Sales & Marketing',
            'LOU070124-460': 'Customer Solutions',
            'KSMZ022122-367': 'Finance, ICT & Admin',
            'MDMA120102-094': 'Davao Branch'
        }

        if user_employee_id not in coordinators:
            return jsonify({'error': 'Access denied. Only coordinators can cancel TOAs.'}), 403

        data = request.json
        reason = data.get('reason', '').strip()

        if not reason:
            return jsonify({'error': 'Cancellation reason is required.'}), 400

        # Get the TOA
        toa = mongo.db.travels.find_one({'toaNumber': toa_number})
        if not toa:
            return jsonify({'error': 'TOA not found.'}), 404

        # Check if TOA is from coordinator's division
        employee = mongo.db.users.find_one({'employeeId': toa.get('employeeId')})
        if not employee:
            return jsonify({'error': 'Employee not found.'}), 404

        employee_division = employee.get('division', '')
        coordinator_division = coordinators[user_employee_id]

        # Handle Finance division variations
        if coordinator_division == 'Finance, ICT & Admin':
            if employee_division not in ['Finance', 'ICT & Admin', 'Finance, ICT & Admin']:
                return jsonify({'error': 'You can only cancel TOAs from your division.'}), 403
        else:
            if employee_division != coordinator_division:
                return jsonify({'error': 'You can only cancel TOAs from your division.'}), 403

        # Check if TOA can be cancelled (not already completed or cancelled)
        if toa.get('approvalStatus') in ['Cancelled']:
            return jsonify({'error': 'TOA is already cancelled.'}), 400

        # Cancel the TOA
        mongo.db.travels.update_one(
            {'toaNumber': toa_number},
            {'$set': {
                'approvalStatus': 'Cancelled',
                'cancelledBy': user.get('fullName'),
                'cancelledById': user_employee_id,
                'cancelledDate': datetime.now().isoformat(),
                'cancellationReason': reason
            }}
        )

        # Cancel associated cash advance if exists
        cash_advance = mongo.db.cash_advances.find_one({'toaNumber': toa_number})
        if cash_advance:
            mongo.db.cash_advances.update_one(
                {'toaNumber': toa_number},
                {'$set': {
                    'status': 'Cancelled',
                    'cancelledBy': user.get('fullName'),
                    'cancelledById': user_employee_id,
                    'cancelledDate': datetime.now().isoformat(),
                    'cancellationReason': reason
                }}
            )

        # Send notification email to employee
        if employee and employee.get('email'):
            msg = Message(
                subject=f'TOA Cancelled: {toa_number}',
                sender='kubotaphportal@gmail.com',
                recipients=[employee['email']]
            )

            msg.body = f"""Dear {toa.get('employee', 'Employee')},

Your Travel Order Authority (TOA: {toa_number}) has been cancelled by {user.get('fullName')}.

Cancellation Reason:
{reason}

Travel Details:
- Destination: {', '.join(toa.get('destinations', []))}
- Travel Dates: {toa.get('startDate')} to {toa.get('endDate')}
- Purpose: {toa.get('purpose', '')}

If you have any questions or concerns about this cancellation, please contact your coordinator.

Best regards,
Travel Authority System
"""
            mail.send(msg)

        return jsonify({'message': 'TOA cancelled successfully.'})

    except Exception as e:
        print(f"Error cancelling TOA: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/toa-reports')
@login_required
def toa_reports_page():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    allowed_ids = ['MTD040323-413', 'LRFT031824-445']
    if user.get('employeeId') not in allowed_ids:
        flash('Access denied. Only authorized employees can access this page.', 'danger')
        return redirect(url_for('homepage'))
    return render_template('toa_reports.html')

@app.route('/api/toa-reports/summary')
@login_required
def get_toa_summary():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    allowed_ids = ['MTD040323-413', 'LRFT031824-445']
    if user.get('employeeId') not in allowed_ids:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Get filter parameters
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        status_filter = request.args.get('status')
        division_filter = request.args.get('division')

        # Build query
        query = {}

        # Date filter
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)  # Include end date
                query['dateFiled'] = {'$gte': start_dt, '$lt': end_dt}
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400

        # Status filter
        if status_filter:
            query['approvalStatus'] = status_filter

        # Division filter (requires joining with users collection)
        if division_filter:
            # Get employee IDs from the specified division
            division_employees = list(mongo.db.users.find(
                {'division': division_filter},
                {'employeeId': 1}
            ))
            employee_ids = [emp['employeeId'] for emp in division_employees]
            query['employeeId'] = {'$in': employee_ids}

        # Get TOA counts
        total_toas = mongo.db.travels.count_documents(query)

        # Status breakdown
        status_pipeline = [
            {'$match': query},
            {'$group': {
                '_id': '$approvalStatus',
                'count': {'$sum': 1}
            }}
        ]
        status_counts = list(mongo.db.travels.aggregate(status_pipeline))

        # Division breakdown
        division_pipeline = [
            {'$match': query},
            {'$lookup': {
                'from': 'users',
                'localField': 'employeeId',
                'foreignField': 'employeeId',
                'as': 'employee_info'
            }},
            {'$unwind': '$employee_info'},
            {'$group': {
                '_id': '$employee_info.division',
                'count': {'$sum': 1}
            }},
            {'$sort': {'count': -1}}
        ]
        division_counts = list(mongo.db.travels.aggregate(division_pipeline))

        # Monthly breakdown for the current year
        current_year = datetime.now().year
        monthly_pipeline = [
            {'$match': {
                **query,
                'dateFiled': {
                    '$gte': datetime(current_year, 1, 1),
                    '$lt': datetime(current_year + 1, 1, 1)
                }
            }},
            {'$group': {
                '_id': {
                    'month': {'$month': '$dateFiled'},
                    'year': {'$year': '$dateFiled'}
                },
                'count': {'$sum': 1}
            }},
            {'$sort': {'_id.month': 1}}
        ]
        monthly_counts = list(mongo.db.travels.aggregate(monthly_pipeline))

        # Cash advance statistics
        ca_pipeline = [
            {'$match': query},
            {'$lookup': {
                'from': 'cash_advances',
                'localField': 'toaNumber',
                'foreignField': 'toaNumber',
                'as': 'cash_advance'
            }},
            {'$group': {
                '_id': None,
                'with_ca': {'$sum': {'$cond': [{'$gt': [{'$size': '$cash_advance'}, 0]}, 1, 0]}},
                'without_ca': {'$sum': {'$cond': [{'$eq': [{'$size': '$cash_advance'}, 0]}, 1, 0]}},
                'total_ca_amount': {
                    '$sum': {
                        '$cond': [
                            {'$gt': [{'$size': '$cash_advance'}, 0]},
                            {'$arrayElemAt': ['$cash_advance.totalAmount', 0]},
                            0
                        ]
                    }
                }
            }}
        ]
        ca_stats = list(mongo.db.travels.aggregate(ca_pipeline))
        ca_data = ca_stats[0] if ca_stats else {'with_ca': 0, 'without_ca': 0, 'total_ca_amount': 0}

        # International vs Domestic
        international_count = mongo.db.travels.count_documents({**query, 'isInternational': True})
        domestic_count = mongo.db.travels.count_documents({**query, 'isInternational': False})

        return jsonify({
            'summary': {
                'total': total_toas,
                'international': international_count,
                'domestic': domestic_count,
                'with_cash_advance': ca_data['with_ca'],
                'without_cash_advance': ca_data['without_ca'],
                'total_cash_advance_amount': ca_data['total_ca_amount']
            },
            'status_breakdown': {item['_id']: item['count'] for item in status_counts},
            'division_breakdown': [{'division': item['_id'], 'count': item['count']} for item in division_counts],
            'monthly_breakdown': [{'month': item['_id']['month'], 'count': item['count']} for item in monthly_counts]
        })

    except Exception as e:
        print(f"Error in get_toa_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toa-reports/detailed')
@login_required
def get_detailed_toa_reports():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    allowed_ids = ['MTD040323-413', 'LRFT031824-445']
    if user.get('employeeId') not in allowed_ids:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Get filter parameters
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        status_filter = request.args.get('status')
        division_filter = request.args.get('division')
        search = request.args.get('search', '').lower()

        # Build query
        query = {}

        # Date filter
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query['dateFiled'] = {'$gte': start_dt, '$lt': end_dt}
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400

        # Status filter
        if status_filter:
            query['approvalStatus'] = status_filter

        # Division filter
        if division_filter:
            division_employees = list(mongo.db.users.find(
                {'division': division_filter},
                {'employeeId': 1}
            ))
            employee_ids = [emp['employeeId'] for emp in division_employees]
            query['employeeId'] = {'$in': employee_ids}

        # Get TOAs with employee and cash advance info
        pipeline = [
            {'$match': query},
            {'$lookup': {
                'from': 'users',
                'localField': 'employeeId',
                'foreignField': 'employeeId',
                'as': 'employee_info'
            }},
            {'$lookup': {
                'from': 'cash_advances',
                'localField': 'toaNumber',
                'foreignField': 'toaNumber',
                'as': 'cash_advance'
            }},
            {'$sort': {'dateFiled': -1}}
        ]

        toas = list(mongo.db.travels.aggregate(pipeline))

        # Format results
        result = []
        for toa in toas:
            employee_info = toa['employee_info'][0] if toa['employee_info'] else {}
            cash_advance = toa['cash_advance'][0] if toa['cash_advance'] else None

            # Apply search filter
            if search:
                searchable_text = ' '.join([
                    toa.get('toaNumber', ''),
                    toa.get('employee', ''),
                    employee_info.get('department', ''),
                    employee_info.get('division', ''),
                    ' '.join(toa.get('destinations', [])),
                    toa.get('purpose', '')
                ]).lower()

                if search not in searchable_text:
                    continue

            result.append({
                'toaNumber': toa.get('toaNumber'),
                'employee': toa.get('employee'),
                'employeeId': toa.get('employeeId'),
                'division': employee_info.get('division', 'Unknown'),
                'department': employee_info.get('department', 'Unknown'),
                'dateFiled': toa.get('dateFiled').isoformat() if toa.get('dateFiled') else '',
                'startDate': toa.get('startDate').isoformat() if toa.get('startDate') else '',
                'endDate': toa.get('endDate').isoformat() if toa.get('endDate') else '',
                'destinations': toa.get('destinations', []),
                'purpose': toa.get('purpose', ''),
                'approvalStatus': toa.get('approvalStatus', 'Pending'),
                'isInternational': toa.get('isInternational', False),
                'hasCashAdvance': cash_advance is not None,
                'cashAdvanceAmount': cash_advance.get('totalAmount', 0) if cash_advance else 0,
                'released': cash_advance.get('released', False) if cash_advance else False,
                'cancelledBy': toa.get('cancelledBy'),
                'cancellationReason': toa.get('cancellationReason'),
                'cancelledDate': toa.get('cancelledDate'),
                'approvers': toa.get('approvers', []),
                'cashAdvanceApprovers': cash_advance.get('approvers', []) if cash_advance else [],
                'cashAdvanceRemarks': cash_advance.get('remarks', '') if cash_advance else '',
                'sentBackRemarks': toa.get('sentBackRemarks', ''),
                'apdpNumber': cash_advance.get('apdpNumber', '') if cash_advance else '',
            })

        return jsonify(result)

    except Exception as e:
        print(f"Error in get_detailed_toa_reports: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toa-reports/export')
@login_required
def export_toa_reports():
    user_id = current_user.id
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

    allowed_ids = ['MTD040323-413', 'LRFT031824-445']
    if user.get('employeeId') not in allowed_ids:
        return jsonify({'error': 'Access denied'}), 403

    try:
        # Get the same data as detailed reports
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        status_filter = request.args.get('status')
        division_filter = request.args.get('division')

        # Build CSV content
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow([
            'TOA Number', 'Employee', 'Employee ID', 'Division', 'Department',
            'Date Filed', 'Start Date', 'End Date', 'Destinations', 'Purpose',
            'Status', 'Type', 'Has Cash Advance', 'Cash Advance Amount',
            'Cash Advance Status', 'Cancelled By', 'Cancellation Reason'
        ])

        # Get data using the same logic as detailed reports
        query = {}
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query['dateFiled'] = {'$gte': start_dt, '$lt': end_dt}

        if status_filter:
            query['approvalStatus'] = status_filter

        if division_filter:
            division_employees = list(mongo.db.users.find(
                {'division': division_filter},
                {'employeeId': 1}
            ))
            employee_ids = [emp['employeeId'] for emp in division_employees]
            query['employeeId'] = {'$in': employee_ids}

        pipeline = [
            {'$match': query},
            {'$lookup': {
                'from': 'users',
                'localField': 'employeeId',
                'foreignField': 'employeeId',
                'as': 'employee_info'
            }},
            {'$lookup': {
                'from': 'cash_advances',
                'localField': 'toaNumber',
                'foreignField': 'toaNumber',
                'as': 'cash_advance'
            }},
            {'$sort': {'dateFiled': -1}}
        ]

        toas = list(mongo.db.travels.aggregate(pipeline))

        for toa in toas:
            employee_info = toa['employee_info'][0] if toa['employee_info'] else {}
            cash_advance = toa['cash_advance'][0] if toa['cash_advance'] else None

            writer.writerow([
                toa.get('toaNumber', ''),
                toa.get('employee', ''),
                toa.get('employeeId', ''),
                employee_info.get('division', 'Unknown'),
                employee_info.get('department', 'Unknown'),
                toa.get('dateFiled').strftime('%Y-%m-%d') if toa.get('dateFiled') else '',
                toa.get('startDate').strftime('%Y-%m-%d') if toa.get('startDate') else '',
                toa.get('endDate').strftime('%Y-%m-%d') if toa.get('endDate') else '',
                ', '.join(toa.get('destinations', [])),
                toa.get('purpose', ''),
                toa.get('approvalStatus', 'Pending'),
                'International' if toa.get('isInternational') else 'Domestic',
                'Yes' if cash_advance else 'No',
                cash_advance.get('totalAmount', 0) if cash_advance else 0,
                cash_advance.get('status', '') if cash_advance else '',
                toa.get('cancelledBy', ''),
                toa.get('cancellationReason', '')
            ])

        output.seek(0)

        # Create response
        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=toa_reports_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        return response

    except Exception as e:
        print(f"Error in export_toa_reports: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/travel/<toa_number>', methods=['DELETE'])
def delete_travel(toa_number):
    mongo.db.travels.delete_one({'toaNumber': toa_number})
    return jsonify({'message': 'Travel request deleted'})


# Serve Swagger UI
SWAGGER_URL = '/docs'
API_URL = '/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Travel Authority API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/approve/<int:request_id>', methods=['GET', 'POST'])
def approve_request(request_id):
    if request_id not in travel_requests:
        flash('Invalid request ID.', 'danger')
        return redirect(url_for('index'))

    request_data = travel_requests[request_id]

    if request.method == 'POST':
        decision = request.form.get('decision')
        remarks = request.form.get('remarks')

        if decision == 'approve':
            flash('Travel request approved!', 'success')
        elif decision == 'reject':
            flash(f'Travel request rejected. Remarks: {remarks}', 'danger')

        return redirect(url_for('index'))

    return render_template('approval.html', data=request_data)


@app.route('/swagger.yaml')
def swagger_yaml():
    return send_from_directory('.', 'swagger.yaml')

if __name__ == '__main__':
    app.run(debug=True)
    # app.run(debug=True, host='0.0.0.0', port=5000)

