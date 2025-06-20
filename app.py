from flask import Flask, render_template, request, redirect, url_for
from models import db, Food, Memo, NotificationSetting
from datetime import datetime, timedelta 
from sqlalchemy import and_
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'AOBfwaoifasi12y98'  # 任意のランダムな文字列(秘密鍵)
db.init_app(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

with app.app_context():
    db.create_all()
# index
@app.route('/')
def index():
    foods = Food.query.order_by(Food.expiry_date).all()
    memo = Memo.query.first()
    today = datetime.today().date()

    # 通知設定（固定で3日に設定。設定画面とか作ってもいいかも？）
    days_before = 3
    notify_until = today + timedelta(days=days_before)
    # 3日以内に賞味期限が来る食品を抽出（今日含む）
    notify_foods = Food.query.filter(
        and_(
            Food.expiry_date >= today,
            Food.expiry_date <= notify_until
        )
    ).order_by(Food.expiry_date).all()
    # 賞味期限が切れている商品を抽出(今日除く)
    expired_foods = Food.query.filter(
        and_(
            Food.expiry_date < today
        )
    ).order_by(Food.expiry_date).all()

    return render_template(
        'index.html',
        foods=foods,
        today=today,
        memo=memo,
        expired_foods=expired_foods,
        notify_foods=notify_foods,
        days_before=days_before
    )
    
# 追加
@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name = request.form['name']
        quantity = request.form['quantity']
        expiry_date = datetime.strptime(request.form['expiry_date'], "%Y-%m-%d").date()

        # 画像の処理
        image = request.files['image']
        image_path = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'static/images/{filename}'

        food = Food(name=name, quantity=quantity, expiry_date=expiry_date, image_path=image_path)
        db.session.add(food)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add.html')

# 検索
@app.route('/search_recipes', methods=['POST'])
def search_recipes():
    selected = request.form.getlist('selected_foods')
    if not selected:
        return redirect(url_for('index'))

    import urllib.parse
    query = " ".join(selected) + " レシピ"
    google_url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    return redirect(google_url)

# 編集
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    food = Food.query.get(id)

    if request.method == 'POST':
        food.name = request.form['name']
        food.quantity = request.form['quantity']
        food.expiry_date = datetime.strptime(request.form['expiry_date'], "%Y-%m-%d").date()

        # 画像の処理
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            food.image_path = f'static/images/{filename}'
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit.html', food=food)

# 削除
@app.route('/delete/<int:id>', methods=['GET'])
def delete(id):
    food = Food.query.get(id)
    if food:
        db.session.delete(food)
        db.session.commit()
    return redirect(url_for('index'))

# メモ
@app.route('/update_memo', methods=['POST'])
def update_memo():
    content = request.form.get('memo_content')
    memo = Memo.query.first()
    if memo:
        memo.content = content
    else:
        memo = Memo(content=content)
        db.session.add(memo)
    db.session.commit()
    return redirect(url_for('index'))

# 画像削除
@app.route('/delete_image/<int:id>', methods=['GET'])
def delete_image(id):
    food = Food.query.get(id)
    if food.image_path:
        # 画像ファイルのパスを生成して削除
        image_path = os.path.join(app.root_path, 'static', 'images', food.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)
        # データベースからも削除
        food.image_path = None
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

# 家計簿機能(?)
# ポイント機能(?)
# 画像機能　バーコード読み取りとかも?
# タグ付けできるように、タグはユーザーが追加できるようにすればいいんじゃないかな() to do
# レシピ提案(多分済)、画像登録(多分済)、読み取り機能
