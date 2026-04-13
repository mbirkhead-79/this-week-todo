from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    tasks = db.relationship('Task', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default='medium')
    due_date = db.Column(db.Date, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
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

    def __repr__(self):
        return f'<Task {self.title}>'


class ActionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    def __repr__(self):
        return f'<ActionItem {self.text}>'
