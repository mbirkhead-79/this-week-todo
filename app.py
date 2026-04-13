from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date
from models import db, Task, Category, ActionItem

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


@app.context_processor
def inject_today():
    return {'today_day': date.today().day}


def sort_tasks(tasks):
    return sorted(tasks, key=lambda t: (
        t.completed,
        Task.PRIORITY_ORDER.get(t.priority, 1),
        t.due_date if t.due_date else date.max,
    ))


@app.route('/')
def inbox():
    tasks = sort_tasks(Task.query.all())
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html',
                           tasks=tasks,
                           categories=categories,
                           page='inbox',
                           page_title='Inbox')


@app.route('/today')
def today():
    tasks = sort_tasks(Task.query.filter(
        Task.due_date == date.today()
    ).all())
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html',
                           tasks=tasks,
                           categories=categories,
                           page='today',
                           page_title='Today')


@app.route('/upcoming')
def upcoming():
    tasks = sort_tasks(Task.query.filter(
        Task.due_date >= date.today()
    ).all())
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html',
                           tasks=tasks,
                           categories=categories,
                           page='upcoming',
                           page_title='Upcoming')


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    tasks = []
    if q:
        tasks = sort_tasks(Task.query.filter(
            Task.title.ilike(f'%{q}%') | Task.description.ilike(f'%{q}%')
        ).all())
    categories = Category.query.order_by(Category.name).all()
    return render_template('index.html',
                           tasks=tasks,
                           categories=categories,
                           page='search',
                           page_title='Search',
                           search_query=q)


@app.route('/filters')
def filters():
    filter_type = request.args.get('filter', 'all')
    category_id = request.args.get('category', None, type=int)

    query = Task.query

    if filter_type == 'active':
        query = query.filter_by(completed=False)
    elif filter_type == 'completed':
        query = query.filter_by(completed=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    tasks = sort_tasks(query.all())
    categories = Category.query.order_by(Category.name).all()

    return render_template('index.html',
                           tasks=tasks,
                           categories=categories,
                           page='filters',
                           page_title='Filters & Labels',
                           current_filter=filter_type,
                           current_category=category_id)


@app.route('/add-task')
def add_task_page():
    categories = Category.query.order_by(Category.name).all()
    return render_template('add_task.html',
                           categories=categories,
                           page='add_task')


def get_or_create_category(category_name, category_id):
    if category_name:
        cat = Category.query.filter_by(name=category_name).first()
        if not cat:
            cat = Category(name=category_name)
            db.session.add(cat)
            db.session.flush()
        return cat.id
    return category_id


def save_action_items(task, form):
    # Clear existing action items
    ActionItem.query.filter_by(task_id=task.id).delete()
    # Add new ones
    items = request.form.getlist('action_items')
    checked = request.form.getlist('action_items_checked')
    for text in items:
        text = text.strip()
        if text:
            item = ActionItem(text=text, task_id=task.id,
                              completed=(text in checked))
            db.session.add(item)


@app.route('/add', methods=['POST'])
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

    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()

    category_id = get_or_create_category(category_name, category_id)

    task = Task(title=title, description=description, priority=priority,
                due_date=due_date, category_id=category_id,
                collaborator_email=collaborator_email)
    db.session.add(task)
    db.session.flush()

    # Save action items
    items = request.form.getlist('action_items')
    for text in items:
        text = text.strip()
        if text:
            item = ActionItem(text=text, task_id=task.id)
            db.session.add(item)

    db.session.commit()
    return redirect(url_for('inbox'))


@app.route('/toggle/<int:task_id>', methods=['POST'])
def toggle(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = not task.completed
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/toggle-action/<int:item_id>', methods=['POST'])
def toggle_action(item_id):
    item = ActionItem.query.get_or_404(item_id)
    item.completed = not item.completed
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/delete/<int:task_id>', methods=['POST'])
def delete(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer or url_for('inbox'))


@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if title:
            task.title = title
        task.description = request.form.get('description', '').strip()
        task.priority = request.form.get('priority', 'medium')
        task.collaborator_email = request.form.get('collaborator_email', '').strip()

        due_date_str = request.form.get('due_date', '').strip()
        task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

        category_name = request.form.get('category_name', '').strip()
        category_id = request.form.get('category_id', '', type=int) or None
        task.category_id = get_or_create_category(category_name, category_id)

        save_action_items(task, request.form)
        db.session.commit()
        return redirect(url_for('inbox'))

    return render_template('edit.html', task=task, categories=categories, page='edit')


@app.route('/delete-category/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    Task.query.filter_by(category_id=cat_id).update({'category_id': None})
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('filters'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
