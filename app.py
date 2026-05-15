import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-qa-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- МОДЕЛИ ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(100), nullable=True)
    questions = db.relationship('Question', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='question', lazy=True, cascade="all, delete-orphan")


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)


# --- МАРШРУТЫ ---

@app.route('/')
def index():
    query = request.args.get('q')
    if query:
        questions = Question.query.filter(Question.title.contains(query)).order_by(Question.date_created.desc()).all()
    else:
        questions = Question.query.order_by(Question.date_created.desc()).all()
    return render_template('index.html', questions=questions)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        if User.query.filter_by(username=username).first():
            flash('Это имя уже занято!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=generate_password_hash(request.form.get('password')))
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/ask', methods=['GET', 'POST'])
@login_required
def ask():
    if request.method == 'POST':
        file = request.files.get('image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_q = Question(
            title=request.form.get('title'),
            content=request.form.get('content'),
            image_file=filename,
            user_id=current_user.id
        )
        db.session.add(new_q)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('ask.html')


@app.route('/question/<int:id>')
def question_detail(id):
    q = Question.query.get_or_404(id)
    return render_template('question.html', question=q)


@app.route('/like/<int:question_id>', methods=['POST'])
@login_required
def like_question(question_id):
    existing_like = Like.query.filter_by(user_id=current_user.id, question_id=question_id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = Like(user_id=current_user.id, question_id=question_id)
        db.session.add(new_like)
    db.session.commit()
    return redirect(request.referrer or url_for('index'))


@app.route('/user/<string:username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    questions = Question.query.filter_by(user_id=user.id).order_by(Question.date_created.desc()).all()
    return render_template('profile.html', user=user, questions=questions)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        file = request.files.get('avatar')
        if file and allowed_file(file.filename):
            filename = secure_filename(f"av_{current_user.id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.avatar = filename
        db.session.commit()
        return redirect(url_for('profile', username=current_user.username))
    return render_template('edit_profile.html')


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        db.create_all()
    app.run(debug=True)
