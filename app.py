from flask import Flask, render_template, request, redirect, url_for
from models import db, Food, Memo, NotificationSetting, Tag
from datetime import datetime, timedelta 
from sqlalchemy import and_
import os
from werkzeug.utils import secure_filename
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

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

# ================== ▼ 追加関数 ▼ ==================
def get_near_expiry_ingredients(days_before: int = 3) -> list[str]:
    """今日から days_before 日以内に期限が来る食材名を返す"""
    today = datetime.today().date()
    until = today + timedelta(days=days_before)
    foods = (Food.query
                  .filter(and_(Food.expiry_date >= today,
                               Food.expiry_date <= until))
                  .order_by(Food.expiry_date)
                  .all())
    return [f.name for f in foods]

# ================== ▼ 新ルート ▼ ==================
@app.route('/generate_recipe')
def generate_recipe():
    """近い期限の食材を使って LLM でレシピを生成し、HTML で返却"""
    # 任意で ?days_before=5 のように上書き可能
    model_name = 'gemini-1.5-flash'
    model = genai.GenerativeModel(model_name)
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    days_before = int(request.args.get('days_before', 3))
    ingredients = get_near_expiry_ingredients(days_before)

    if not ingredients:
        # 期限食材が無いときはメッセージだけ表示
        return render_template('recipes.html',
                               recipes=[],
                               message='期限が近い食材がありません。')

    # === LLM 呼び出し ===
    prompt = (
        "次のフォーマットで純粋な JSON（前後説明・ ```json``` 不要）だけを返してください。\n"
        "{\"recipes\":[{\"title\":...,\"ingredients\":[...],\"steps\":[...]}]}\n\n"
        "以下の食材を必ず使い切るレシピを 3 品、日本語で JSON 形式で返してください。"
        "各レシピは title, ingredients, steps を含むオブジェクトとし、"
        "JSON のトップレベルキーは recipes とします。\n\n"
        "なお、下記に示す食材の内使用しないものに関してはingredientsに書く必要はありません。"
        "ingredientsには材料の必要量も記入し、titleには何人前かも記入してください"
        f"食材: {', '.join(ingredients)}"
    )

    try:
        response = model.generate_content(prompt)
        content = response.text
        try:
            data = json.loads(content)          # LLM が出力した JSON をパース
        except:
            data = parse_llm_json(content)
        recipes = data.get("recipes", [])
    except Exception as e:
        # 失敗時は空で返す
        print("[Recipe‑LLM‑Error]", e)
        return render_template('recipes.html',
                               recipes=[],
                               message='レシピ生成に失敗しました。時間をおいて再試行してください。')

    return render_template('recipes.html', recipes=recipes)

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

def parse_llm_json(content: str) -> dict:
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
    return json.loads(raw)

if __name__ == '__main__':
    app.run(debug=True)

# 家計簿機能(?)
# ポイント機能(?)
# 画像機能　バーコード読み取りとかも?
# タグ付けできるように、タグはユーザーが追加できるようにすればいいんじゃないかな(多分済)
# レシピ提案(多分済)、画像登録(多分済)、読み取り機能
