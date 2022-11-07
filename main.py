from functools import wraps

from flask import Flask , render_template , redirect , url_for , flash , request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegistrationForm, LoginForm, CommentForm
from flask_gravatar import Gravatar



app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False )
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=True)
    # relationship linked by same name like X
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="commentator")

# db.create_all()


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # relationship with User
    author_id = db.Column(db.Integer , db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
#      BlogPost can have many associated Comment objects.
    comments = relationship("Comment", back_populates="parent_post")
# db.create_all()

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False) # stringfield = 255 characters, a textfield  30,000 characters.
#     relationship with user
    commentator = relationship("User", back_populates="comments")
#     many to many stuff
    parent_post = relationship("BlogPost", back_populates="comments")
#     #     setup foreign keys
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    post_id = db.Column(db.Integer,db.ForeignKey("blog_posts.id"))
# db.create_all()

# comment section images via gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# run create all dbs first without having to comment out afterwards
# also suggested fix to (sqlite3.OperationalError) no such column: blog_posts.author_id
@app.before_first_request
def create_tables():
    db.create_all()

# make is_authenticated available to the whole program without passed is_logged repeatedly
# pass

# setup login manager
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # we add query since we are getting it from the db
    return User.query.get(int(user_id))

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user )


@app.route('/register', methods = ["GET", "POST"])
def register():
    reg_form = RegistrationForm()
    if reg_form.validate_on_submit():
        new_user = User(
            name = reg_form.name.data,
            email = reg_form.email.data,
            password = generate_password_hash(reg_form.password.data,method="pbkdf2:sha256", salt_length=8)
        )
        if User.query.filter_by(email=new_user.email).first():
            flash("Possible Duplicate. Try Logging in")
            return redirect(url_for("login"))
        else:
            db.session.add(new_user)
            db.session.commit()
            flash("Registation Successful")
            # login the newly registered member
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=reg_form)


@app.route('/login', methods = ["GET","POST"] )
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(user.password,form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                form.email.data = user.email
                flash("Credentials not accurate!")
        else:
            form.email.data = ""
            flash("Credentials not accurate!")
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in to comment.")
            return redirect(url_for("login"))
        else:
            new_comment = Comment(
                text=form.comment_text.data,
                author_id=current_user.id,
                post_id=requested_post.id
            )
            db.session.add(new_comment)
            db.session.commit()
    #         clear comment section
            form.comment_text.data = ""
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# decorator function to check if the user is admin
def admin_only(f):
    @wraps(f)  # why we use @wraps(function) We can apply both decorators as below
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_anonymous:
            return redirect(url_for('login', next=request.url))
        elif current_user.id == 1:
            return f(*args, **kwargs) #Why do we need the *args, **kwargs though? My code works even without them: add_post function will still work edit_post and delete_post won't work without post id
        else:
            return abort(403)

    return decorated_function


@app.route("/new-post", methods=["GET","POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = post.author
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user = current_user)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
