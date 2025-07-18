import re
from flask import Flask, render_template, render_template_string, request, redirect, url_for
from models import db, Food, Memo, NotificationSetting, Tag
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
   
#tagで絞り込み
@app.route('/filter_by_tag')
def filter_by_tag():
    tag_name = request.args.get('tag')
    if not tag_name:
        return redirect(url_for('index'))

    tag = Tag.query.filter_by(name=tag_name).first()
    if not tag:
        return redirect(url_for('index'))

    foods = tag.foods.order_by(Food.expiry_date).all()
    memo = Memo.query.first()
    today = datetime.today().date()

    days_before = 3
    notify_until = today + timedelta(days=days_before)
    notify_foods = Food.query.filter(Food.expiry_date.between(today, notify_until)).order_by(Food.expiry_date).all()
    expired_foods = Food.query.filter(Food.expiry_date < today).order_by(Food.expiry_date).all()

    return render_template(
        'index.html',
        foods=foods,
        today=today,
        memo=memo,
        expired_foods=expired_foods,
        notify_foods=notify_foods,
        days_before=days_before,
        filtered_tag=tag_name,
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
        
        #tag処理
        tags_input = request.form['tags']
        tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
        tags = []
        for t in tag_names:
            tag = Tag.query.filter_by(name=t).first()
            if not tag:
                tag = Tag(name=t)
                db.session.add(tag)
        tags.append(tag)
        
        food = Food(name=name, quantity=quantity, expiry_date=expiry_date, image_path=image_path, tags=tags)
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
        
        #tag処理
        tags_input = request.form['tags']
        tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
        tags = []
        for name in tag_names:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            tags.append(tag)
            food.tags = tags

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


@app.route('/analyze_imageform/<int:id>', methods=['GET', 'POST'])
def analyze_image_form(id):
    food = Food.query.get(id)

    if request.method == 'POST':
        # 画像の処理
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            food.image_path = f'static/images/{filename}'
        db.session.commit()

        return redirect(url_for('analyzed_tags', id=id))
        # return analyzed_tags(id)

    return render_template('analyze_image_form.html', food=food)

@app.route('/analyzed_tags/<int:id>', methods=['GET', 'POST'])
def analyzed_tags(id):
    food = Food.query.get(id)

    if request.method == 'POST':
        tag_names = request.form.getlist('tags')
        print(tag_names)
        tags = []
        for name in tag_names:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
            tags.append(tag)
            food.tags = tags
        db.session.commit()
        return redirect(url_for('index'))
    #########################################################################
    print("asking to Gemini")
    import google.generativeai as genai
    import PIL

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    image_part = PIL.Image.open(food.image_path)
    prompt = """この画像に含まれている食品について、以下の形式で$name$に食品名が並ぶように結果だけ返してください。
<input type="checkbox" name="tags" value="$name$">
<label for="$num$">$name$</label><br>
    """
    response = model.generate_content([prompt, image_part])

    print(response.text)
    print("Gemini responded")
    return render_template_string(f"""
{{% extends 'layout.html' %}}
{{% block content %}}
<h2>食品タグ追加</h2>
                                  
<div><img src="{ url_for('static', filename='images/' + food.image_path.split('/')[-1]) }"
style="max-height:100px;"></div>
<form method="POST" enctype="multipart/form-data">
{parse_llm_code_block(response.text)}
<button type="submit" class="btn btn-primary">タグ追加</button>
</form>
{{% endblock %}}
""")

def parse_llm_code_block(content: str) -> dict:
    """
    ```json ... ``` 付きで返ってきた LLM 出力を
    純粋な Python dict に変換するヘルパー。
    """
    if not isinstance(content, str):
        raise TypeError("content must be str")

    # 前後空白・改行を削る
    raw = content.strip()

    # 先頭が ``` で始まるならフェンスを除去
    if raw.startswith("```"):
        # 1行目の ```json などを落とす
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw, count=1)
        # 末尾の ``` を落とす
        raw = re.sub(r"\s*```$", "", raw, count=1)

    # さらに余分な改行・空白を削る
    raw = raw.strip()

    # JSON → Python dict
    return raw

if __name__ == '__main__':
    app.run(debug=True)

# 家計簿機能(?)
# ポイント機能(?)
# 画像機能　バーコード読み取りとかも?
# タグ付けできるように、タグはユーザーが追加できるようにすればいいんじゃないかな(多分済)
# レシピ提案(多分済)、画像登録(多分済)、読み取り機能
