from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()

STATUSES = ['todo', 'in_progress', 'done']
STATUS_LABELS = {'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship('Task', backref='owner', lazy=True, cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tasks = db.relationship('Task', backref='category', lazy=True)

    __table_args__ = (db.UniqueConstraint('name', 'user_id'),)

    def __repr__(self):
        return f'<Category {self.name}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    completed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='todo')
    priority = db.Column(db.String(10), default='medium')
    due_date = db.Column(db.Date, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    collaborator_email = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    action_items = db.relationship('ActionItem', backref='task', lazy=True,
                                   cascade='all, delete-orphan', order_by='ActionItem.id')

    PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

    @property
    def is_overdue(self):
        return self.due_date is not None and self.due_date < date.today() and not self.completed

    @property
    def action_items_progress(self):
        total = len(self.action_items)
        if total == 0:
            return None
        done = sum(1 for item in self.action_items if item.completed)
        return f'{done}/{total}'

    @property
    def action_items_percent(self):
        total = len(self.action_items)
        if total == 0:
            return 0
        done = sum(1 for item in self.action_items if item.completed)
        return int((done / total) * 100)

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description or '',
            'completed': self.completed,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else '',
            'due_date_display': self.due_date.strftime('%b %d') if self.due_date else '',
            'category': self.category.name if self.category else '',
            'collaborator_email': self.collaborator_email or '',
            'is_overdue': self.is_overdue,
            'action_items': [{'id': ai.id, 'text': ai.text, 'completed': ai.completed} for ai in self.action_items],
            'action_items_progress': self.action_items_progress,
            'action_items_percent': self.action_items_percent,
        }

    def __repr__(self):
        return f'<Task {self.title}>'


class ActionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    def __repr__(self):
        return f'<ActionItem {self.text}>'
