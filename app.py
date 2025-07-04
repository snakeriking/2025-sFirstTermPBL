from flask import Flask, render_template, request, redirect, url_for
from models import db, Food, Memo, NotificationSetting, Tag
from datetime import datetime, timedelta 
from sqlalchemy import and_
import os
from werkzeug.utils import secure_filename
import random

TIPS = [
    "にんじんの栄養は皮の近くに多い。皮を厚くむくと栄養が減ってしまう。",
    "トマトは冷やしすぎると甘味が落ちる。常温保存がおすすめ。",
    "ブロッコリーは茎の部分にも栄養がある。皮をむけばおいしく食べられる。",
    "ほうれん草は茹でるとシュウ酸が減り、カルシウムの吸収を妨げにくくなる。",
    "りんごの皮には食物繊維とポリフェノールがたっぷり。皮ごと食べると◎。",
    "バナナは熟すほど抗酸化作用が高まる。黒い斑点は甘くて栄養の証！",
    "鶏むね肉は加熱しすぎるとパサつく。低温でじっくり火を通すとジューシーに。",
    "魚の皮にはDHAやコラーゲンが多く含まれている。パリッと焼いて食べよう。",
    "豆腐はたんぱく質だけでなくカルシウムも豊富。成長期にもおすすめ。",
    "卵の黄身にはビタミンDが含まれていて、骨の健康に役立つ。",
    "白米を玄米に変えるだけで、食物繊維やビタミンB群の摂取量がアップする。",
    "冷えたごはんには“レジスタントスターチ”が増え、血糖値が上がりにくくなる。",
    "パンよりおにぎりの方が腹持ちが良いと感じる人も。理由は水分量と消化速度。",
    "醤油は開封後、冷蔵庫保存が基本。常温だと風味がどんどん落ちる。",
    "だしを使うと塩分を控えやすい。うま味で満足感がアップするから。",
    "よく噛むことで脳が活性化され、食べすぎ防止にもなる。",
    "朝食を抜くと1日を通して血糖値が乱れやすくなる。バナナ1本でもOK。",
    "“彩りがある食事”は自然と栄養バランスも良くなる。",
    "食材を買いすぎると廃棄も増える。週1で“冷蔵庫チェック日”を作ろう。",
    "冷蔵庫の中は詰めすぎると冷気が回らず、食材が傷みやすくなる。",
    "食材は“先入れ・先出し”が基本。古い順に使おう。",
    "野菜は新聞紙やキッチンペーパーで包むと、保存期間がぐっと伸びる。",
    "切ったネギは冷凍OK！そのまま味噌汁や炒め物に使える。"
]


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

    tip = random.choice(TIPS)
    return render_template(
        'index.html',
        foods=foods,
        today=today,
        memo=memo,
        expired_foods=expired_foods,
        notify_foods=notify_foods,
        days_before=days_before,
        tip=tip
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

if __name__ == '__main__':
    app.run(debug=True)

# 家計簿機能(?)
# ポイント機能(?)
# 画像機能　バーコード読み取りとかも?
# タグ付けできるように、タグはユーザーが追加できるようにすればいいんじゃないかな(多分済)
# レシピ提案(多分済)、画像登録(多分済)、読み取り機能
