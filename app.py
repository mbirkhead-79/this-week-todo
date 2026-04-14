import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, date
from models import db, User, Task, Category, ActionItem, STATUSES, STATUS_LABELS

app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///todo.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_globals():
    return {'today_day': date.today().day}


def sort_tasks(tasks):
    return sorted(tasks, key=lambda t: (
        t.completed,
        Task.PRIORITY_ORDER.get(t.priority, 1),
        t.due_date if t.due_date else date.max,
    ))


def user_tasks():
    return Task.query.filter_by(user_id=current_user.id)


def user_categories():
    return Category.query.filter_by(user_id=current_user.id).order_by(Category.name)


# --- Auth ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', page='login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
        else:
            user = User(email=email, name=name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
    return render_template('register.html', page='register')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- Dashboard ---
@app.route('/')
@login_required
def dashboard():
    all_tasks = user_tasks().all()
    today_date = date.today()

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.completed)
    overdue = sum(1 for t in all_tasks if t.is_overdue)
    due_today = [t for t in all_tasks if t.due_date == today_date and not t.completed]
    high_priority = [t for t in all_tasks if t.priority == 'high' and not t.completed]
    status_counts = {s: sum(1 for t in all_tasks if t.status == s) for s in STATUSES}
    recent = sorted(all_tasks, key=lambda t: t.created_at or datetime.min, reverse=True)[:5]
    categories = user_categories().all()

    return render_template('dashboard.html',
                           page='dashboard',
                           total=total, completed=completed, overdue=overdue,
                           due_today=due_today, high_priority=high_priority,
                           status_counts=status_counts, recent=recent,
                           categories=categories,
                           completion_pct=int((completed / total * 100)) if total else 0)


@app.route('/inbox')
@login_required
def inbox():
    tasks = sort_tasks(user_tasks().all())
    categories = user_categories().all()
    return render_template('index.html', tasks=tasks, categories=categories,
                           page='inbox', page_title='Inbox')


@app.route('/board')
@login_required
def board():
    columns = {}
    for status in STATUSES:
        columns[status] = {
            'label': STATUS_LABELS[status],
            'tasks': sort_tasks(user_tasks().filter_by(status=status).all())
        }
    categories = user_categories().all()
    return render_template('board.html', columns=columns, statuses=STATUSES,
                           categories=categories, page='board', page_title='Board')


@app.route('/api/task/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    new_status = data.get('status')
    if new_status in STATUSES:
        task.status = new_status
        task.completed = (new_status == 'done')
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 400


@app.route('/api/task/<int:task_id>')
@login_required
def get_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    return jsonify(task.to_dict())


@app.route('/today')
@login_required
def today():
    tasks = sort_tasks(user_tasks().filter(Task.due_date == date.today()).all())
    categories = user_categories().all()
    return render_template('index.html', tasks=tasks, categories=categories,
                           page='today', page_title='Today')


@app.route('/upcoming')
@login_required
def upcoming():
    tasks = sort_tasks(user_tasks().filter(Task.due_date >= date.today()).all())
    categories = user_categories().all()
    return render_template('index.html', tasks=tasks, categories=categories,
                           page='upcoming', page_title='Upcoming')


@app.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    tasks = []
    if q:
        tasks = sort_tasks(user_tasks().filter(
            Task.title.ilike(f'%{q}%') | Task.description.ilike(f'%{q}%')
        ).all())
    categories = user_categories().all()
    return render_template('index.html', tasks=tasks, categories=categories,
                           page='search', page_title='Search', search_query=q)


@app.route('/filters')
@login_required
def filters():
    filter_type = request.args.get('filter', 'all')
    category_id = request.args.get('category', None, type=int)
    query = user_tasks()
    if filter_type == 'active':
        query = query.filter_by(completed=False)
    elif filter_type == 'completed':
        query = query.filter_by(completed=True)
    if category_id:
        query = query.filter_by(category_id=category_id)
    tasks = sort_tasks(query.all())
    categories = user_categories().all()
    return render_template('index.html', tasks=tasks, categories=categories,
                           page='filters', page_title='Filters & Labels',
                           current_filter=filter_type, current_category=category_id)


@app.route('/add-task')
@login_required
def add_task_page():
    categories = user_categories().all()
    return render_template('add_task.html', categories=categories, page='add_task')


def get_or_create_category(category_name, category_id):
    if category_name:
        cat = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
        if not cat:
            cat = Category(name=category_name, user_id=current_user.id)
            db.session.add(cat)
            db.session.flush()
        return cat.id
    return category_id


def save_action_items(task, form):
    ActionItem.query.filter_by(task_id=task.id).delete()
    items = request.form.getlist('action_items')
    checked = request.form.getlist('action_items_checked')
    for text in items:
        text = text.strip()
        if text:
            db.session.add(ActionItem(text=text, task_id=task.id, completed=(text in checked)))


@app.route('/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    if not title:
        return redirect(url_for('inbox'))
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium')
    collaborator_email = request.form.get('collaborator_email', '').strip()
    due_date_str = request.form.get('due_date', '').strip()
    category_name = request.form.get('category_name', '').strip()
    category_id = request.form.get('category_id', '', type=int) or None
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
    category_id = get_or_create_category(category_name, category_id)

    task = Task(title=title, description=description, priority=priority,
                due_date=due_date, category_id=category_id,
                collaborator_email=collaborator_email, status='todo',
                user_id=current_user.id)
    db.session.add(task)
    db.session.flush()

    items = request.form.getlist('action_items')
    for text in items:
        text = text.strip()
        if text:
            db.session.add(ActionItem(text=text, task_id=task.id))

    db.session.commit()
    return redirect(url_for('inbox'))


@app.route('/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.completed = not task.completed
    task.status = 'done' if task.completed else 'todo'
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/toggle-action/<int:item_id>', methods=['POST'])
@login_required
def toggle_action(item_id):
    item = ActionItem.query.get_or_404(item_id)
    task = Task.query.filter_by(id=item.task_id, user_id=current_user.id).first_or_404()
    item.completed = not item.completed
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    categories = user_categories().all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if title:
            task.title = title
        task.description = request.form.get('description', '').strip()
        task.priority = request.form.get('priority', 'medium')
        task.collaborator_email = request.form.get('collaborator_email', '').strip()
        task.status = request.form.get('status', task.status)
        task.completed = (task.status == 'done')
        due_date_str = request.form.get('due_date', '').strip()
        task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        category_name = request.form.get('category_name', '').strip()
        category_id = request.form.get('category_id', '', type=int) or None
        task.category_id = get_or_create_category(category_name, category_id)
        save_action_items(task, request.form)
        db.session.commit()
        return redirect(request.form.get('return_to') or url_for('inbox'))
    return render_template('edit.html', task=task, categories=categories, page='edit')


@app.route('/delete-category/<int:cat_id>', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.filter_by(id=cat_id, user_id=current_user.id).first_or_404()
    Task.query.filter_by(category_id=cat_id, user_id=current_user.id).update({'category_id': None})
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('filters'))


@app.route('/api/notifications')
@login_required
def notifications():
    today_date = date.today()
    due_today = user_tasks().filter(Task.due_date == today_date, Task.completed == False).count()
    overdue = user_tasks().filter(Task.due_date < today_date, Task.completed == False).count()
    return jsonify({'due_today': due_today, 'overdue': overdue})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
