 
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone
from flask_migrate import Migrate  # Flask-Migrate'i içeri aktarıyoruz
import re
import random
from flask import jsonify
import uuid


DB_NAME = 'database.db'
app = Flask(__name__)


app.config['SECRET_KEY'] = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'


db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Migrate nesnesini oluşturuyoruz

class Students(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    questions = db.relationship('Questions', backref='student_question', lazy=True)  # Change 'student' to 'student_question'


class Questions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    answeroption1 = db.Column(db.String(100), nullable=False)
    answeroption2 = db.Column(db.String(100), nullable=False)
    answeroption3 = db.Column(db.String(100), nullable=False)
    answeroption4 = db.Column(db.String(100), nullable=False)
    erklaerung = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    correct_answer = db.Column(db.Integer, nullable=False)

course = db.relationship('Course', backref='questions_list')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

# ✅ MultiplayerGame tablosunu da ekleyelim
class MultiplayerGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(36), unique=True, nullable=False)
    player1 = db.Column(db.String(100), nullable=False)
    player2 = db.Column(db.String(100), nullable=False)
    questions = db.Column(db.Text, nullable=False)
    score1 = db.Column(db.Integer, default=0)
    score2 = db.Column(db.Integer, default=0)

class MultiplayerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(36), db.ForeignKey('multiplayer_game.game_id'), nullable=False)
    sender_email = db.Column(db.String(100), nullable=False)  # Oyunu başlatan kişi
    receiver_email = db.Column(db.String(100), nullable=False)  # Davet edilen kişi
    status = db.Column(db.String(20), default="Beklemede")  # Beklemede, Kabul Edildi, Reddedildi

class SoloQuiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(36), unique=True, nullable=False)
    player_email = db.Column(db.String(100), nullable=False)
    questions = db.Column(db.Text, nullable=False)  # 📌 Soruların ID'lerini string olarak saklıyoruz
    score = db.Column(db.Integer, default=0)
    date_played = db.Column(db.DateTime, default=datetime.utcnow)



 


    
@app.route('/')
def index():
    me = None
    if "email" in session:
        me = Students.query.filter_by(email=session["email"]).first()
    return render_template('index.html', me=me)  # ✅ Kullanıcı bilgisi eklendi

@app.route('/anfragen', methods=['GET', 'POST'])
def anfragen():
    if "email" not in session:
        flash("Bitte loggen Sie sich ein.", "danger")
        return redirect(url_for("login"))

    # Kullanıcının gelen multiplayer isteklerini getir
    requests = MultiplayerRequest.query.filter_by(receiver_email=session["email"], status="Beklemede").all()

    if request.method == "POST":
        game_id = request.form.get("game_id")
        action = request.form.get("action")

        request_entry = MultiplayerRequest.query.filter_by(game_id=game_id, receiver_email=session["email"]).first()

        if action == "Kabul Et":
            request_entry.status = "Kabul Edildi"
            db.session.commit()
            session["multiplayer_game_id"] = game_id  # Oyunu oturuma kaydet
            return redirect(url_for("multiplayer_quiz"))

        elif action == "Reddet":
            request_entry.status = "Reddedildi"
            db.session.commit()

    return render_template("anfragen.html", requests=requests)




@app.route('/quiz')
def quiz():
    if "email" not in session:
        flash("Bitte zuerst Login", "warning")
        return redirect(url_for("login"))

    user_email = session["email"]

    # SoloQuiz'leri ve Multiplayer Quiz'leri çek
    solo_quizzes = SoloQuiz.query.filter_by(player_email=user_email).order_by(SoloQuiz.date_played.desc()).limit(10).all()
    multiplayer_games = MultiplayerGame.query.filter(
        (MultiplayerGame.player1 == user_email) | (MultiplayerGame.player2 == user_email)
    ).order_by(MultiplayerGame.id.desc()).limit(10).all()

    # ✅ solo_quizzes VE multiplayer_games değişkenlerini şablona gönderiyoruz
    return render_template('quiz.html', solo_quizzes=solo_quizzes, multiplayer_games=multiplayer_games)












@app.route('/delete_quiz/<string:quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    if "email" not in session:
        flash("Bitte Einloggen", "danger")
        return redirect(url_for("login"))

    # ✅ **SoloQuiz tablosundan silme işlemi**
    quiz = SoloQuiz.query.filter_by(game_id=quiz_id, player_email=session["email"]).first()
    
    if not quiz:
        flash("Quiz nicht gefunden", "danger")
        return redirect(url_for("quiz"))

    db.session.delete(quiz)
    db.session.commit()

    
    return redirect(url_for("quiz"))

@app.route('/delete_multiplayer_quiz/<string:game_id>', methods=['POST'])
def delete_multiplayer_quiz(game_id):
    if "email" not in session:
        flash("Bitte Einloggen", "danger")
        return redirect(url_for("login"))

    game = MultiplayerGame.query.filter(
        (MultiplayerGame.game_id == game_id) & 
        ((MultiplayerGame.player1 == session["email"]) | (MultiplayerGame.player2 == session["email"]))
    ).first()

    if not game:
        flash("Kein Quiz gefunden oder keine Berechtigung zum Löschen!", "danger")
        return redirect(url_for("quiz"))

    db.session.delete(game)
    db.session.commit()

    
    return redirect(url_for("quiz"))

@app.route('/quiz_details/<string:quiz_id>')
def quiz_details(quiz_id):
    if "email" not in session:
        flash("Bitte Einloggen", "warning")
        return redirect(url_for("login"))

    # 📌 Eğer UUID formatındaysa multiplayer quizdir
    if len(quiz_id) > 10:
        multiplayer_quiz = MultiplayerGame.query.filter_by(game_id=quiz_id).first()

        if not multiplayer_quiz:
            flash("Multiplayer quiz nicht gefunden!", "danger")
            return redirect(url_for("quiz"))

        # 📌 Soruların ID'lerini çek
        try:
            question_ids = list(map(int, multiplayer_quiz.questions.split(",")))
        except ValueError:
            flash("Error Fragen Upload", "danger")
            return redirect(url_for("quiz"))

        # 📌 Soruları açıklama (`erklaerung`) ile birlikte çek
        questions = Questions.query.with_entities(
            Questions.id, 
            Questions.question, 
            Questions.answeroption1, 
            Questions.answeroption2, 
            Questions.answeroption3, 
            Questions.answeroption4, 
            Questions.correct_answer,
            Questions.erklaerung  # ✅ Açıklamayı da çekiyoruz
        ).filter(Questions.id.in_(question_ids)).all()

        return render_template("quiz_details.html", multiplayer_quiz=multiplayer_quiz, questions=questions, single_quiz=None)

    # 📌 Eğer `quiz_id` tek kişilik quizse (SoloQuiz tablosuna kayıtlı)
    else:
        solo_quiz = SoloQuiz.query.filter_by(game_id=quiz_id).first()
        if not solo_quiz:
            flash("Allein Quiz nicht gefunden", "danger")
            return redirect(url_for("quiz"))

        question_ids = list(map(int, solo_quiz.questions.split(",")))

        single_quiz_questions = Questions.query.with_entities(
            Questions.id, 
            Questions.question, 
            Questions.answeroption1, 
            Questions.answeroption2, 
            Questions.answeroption3, 
            Questions.answeroption4, 
            Questions.correct_answer,
            Questions.erklaerung  # ✅ Açıklamayı da çekiyoruz
        ).filter(Questions.id.in_(question_ids)).all()

        return render_template("quiz_details.html", single_quiz=single_quiz_questions, multiplayer_quiz=None)

@app.route('/select_course', methods=['GET', 'POST'])
def select_course():
    if request.method == "POST":
        course_id = request.form.get("course_id")
        
        # Seçilen kursa ait 10 rastgele soruyu al
        questions = Questions.query.filter_by(course_id=course_id).all()
        random.shuffle(questions)  # Soruları karıştır
        questions = questions[:10]  # İlk 10 soruyu seç
        
        if not questions:
            flash("Not Enough Question", "warning")
            return redirect(url_for("quiz"))
        
        return render_template("quiz_questions.html", questions=questions, course_id=course_id)

        
    courses = Course.query.all()  # Kullanıcının seçebileceği kursları getir
    return render_template("select_course.html", courses=courses)
    from datetime import datetime, timezone


@app.route('/start_solo_quiz', methods=['POST'])
def start_solo_quiz():
    if "email" not in session:
        flash("Bitte Einloggen", "danger")
        return redirect(url_for("login"))

    course_id = request.form.get("course_id")
    
    if not course_id:
        flash("Bitte Kurs Auswählen", "warning")
        return redirect(url_for("select_course"))

    questions = Questions.query.filter_by(course_id=course_id).order_by(db.func.random()).limit(10).all()

    if not questions:
        flash("Not Enough Question", "warning")
        return redirect(url_for("select_course"))

    return render_template("quiz_questions.html", questions=questions, course_id=course_id)











@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if "email" not in session:
        flash("Bitte Einloggen", "danger")
        return redirect(url_for("login"))

    user_email = session["email"]
    correct_answers = 0
    total_score = 0
    total_questions = 0
    answered_questions = []

    for key, value in request.form.items():
        if key.startswith("question_"):
            question_id = int(key.split("_")[1])
            selected_answer = int(value)

            question = Questions.query.get(question_id)
            if question:
                is_correct = (question.correct_answer == selected_answer)
                if is_correct:
                    correct_answers += 1
                    total_score += 5

                answered_questions.append({
                    "question": question.question,
                    "answeroption1": question.answeroption1,
                    "answeroption2": question.answeroption2,
                    "answeroption3": question.answeroption3,
                    "answeroption4": question.answeroption4,
                    "selected_answer": selected_answer,
                    "correct_answer": question.correct_answer,
                    "erklaerung": question.erklaerung
                })

            total_questions += 1

    # **Sonuçları session'da sakla**
    session["quiz_results"] = answered_questions
    session["total_score"] = total_score

    return redirect(url_for("quiz_results"))

@app.route('/quiz_results')
def quiz_results():
    if "quiz_results" not in session or "total_score" not in session:
        flash("Ergebniss nicht gefunden", "danger")
        return redirect(url_for("quiz"))

    return render_template("quiz_results.html")






@app.route('/multiplayer', methods=['GET', 'POST'])
def multiplayer():
    if "email" not in session:
        flash("Bitte loggen Sie sich ein.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        friend_email = request.form.get("friend_email").strip()
        course_id = request.form.get("course_id")
        friend = Students.query.filter_by(email=friend_email).first()

        if not friend:
            flash("Freund nicht gefunden!", "danger")
            return redirect(url_for("multiplayer"))

        # Oyun ID oluştur
        game_id = str(uuid.uuid4())

        # Seçilen derse ait 10 rastgele soruyu getir
        questions = Questions.query.filter_by(course_id=course_id).order_by(db.func.random()).limit(10).all()
        question_ids = [q.id for q in questions]

        if not questions:
            flash("Not Enough Question!", "warning")
            return redirect(url_for("multiplayer"))

        # Multiplayer oyununu veritabanına ekle
        new_game = MultiplayerGame(
            game_id=game_id,
            player1=session["email"],
            player2=friend_email,
            questions=",".join(map(str, question_ids))
        )
        db.session.add(new_game)

        # Multiplayer isteğini arkadaşına ekle
        new_request = MultiplayerRequest(
            game_id=game_id,
            sender_email=session["email"],
            receiver_email=friend_email,
            status="Beklemede"
        )
        db.session.add(new_request)

        db.session.commit()

        # 📌 Multiplayer oyun ID'sini oturuma ekleyelim
        session["multiplayer_game_id"] = game_id

        flash("Quiz Anfrage gesendet", "success")
        return redirect(url_for("multiplayer_quiz"))  # ✅ Oyunu başlat!

    courses = Course.query.all()
    return render_template("multiplayer.html", courses=courses)




@app.route('/multiplayer_quiz', methods=['GET', 'POST'])
def multiplayer_quiz():
    if "email" not in session:
        flash("Bitte loggen Sie sich ein.", "danger")
        return redirect(url_for("login"))

    if "multiplayer_game_id" not in session:
        flash("Multiplayer-Session nicht gefunden.", "danger")
        return redirect(url_for("multiplayer"))

    game = MultiplayerGame.query.filter_by(game_id=session["multiplayer_game_id"]).first()
    if not game:
        flash("Multiplayer-Spiel nicht gefunden.", "danger")
        return redirect(url_for("multiplayer"))

    question_ids = list(map(int, game.questions.split(",")))
    questions = Questions.query.filter(Questions.id.in_(question_ids)).all()

    if request.method == "POST":
        total_score = 0
        for question in questions:
            user_answer = request.form.get(f"question_{question.id}")
            if user_answer and int(user_answer) == question.correct_answer:
                total_score += 5

        # ✅ Multiplayer quiz geçmişine kaydet
        if session["email"] == game.player1:
            game.score1 = total_score
        else:
            game.score2 = total_score

        db.session.commit()
        return redirect(url_for("multiplayer_results"))

    return render_template("multiplayer_quiz.html", questions=questions)


    


@app.route("/start_multiplayer", methods=["POST"])
def start_multiplayer():
    if "email" not in session:
        flash("Bitte Einloggen", "error")
        return redirect(url_for("login"))

    player1_email = session["email"]  # Oturum açan kullanıcı
    player2_email = request.form.get("player2_email").strip()  # Formdan gelen arkadaş emaili

    if not player2_email:
        flash("Bitte e-mail des Freunds eingeben", "error")
        return redirect(url_for("quiz"))

    if player1_email == player2_email:
        flash("Quiz nicht erlaubt", "error")
        return redirect(url_for("quiz"))

    # Oyun için benzersiz bir ID oluştur
    game_id = str(uuid.uuid4())

    # 10 rastgele soru seç
    questions = Questions.query.order_by(db.func.random()).limit(10).all()
    question_ids = [q.id for q in questions]

    if not questions:
        flash("Not Enough Question", "error")
        return redirect(url_for("quiz"))

    # Yeni bir multiplayer oyunu oluştur
    game = MultiplayerGame(
        game_id=game_id,
        player1=player1_email,
        player2=player2_email,
        questions=",".join(map(str, question_ids)),  # Soruları string olarak kaydet
        score1=0,
        score2=0
    )
    db.session.add(game)

    # Arkadaşına quiz isteği gönder
    new_request = MultiplayerRequest(
        game_id=game_id,
        sender_email=player1_email,
        receiver_email=player2_email,
        status="Beklemede"
    )
    db.session.add(new_request)

    db.session.commit()

    flash("Quiz Anfrage gesendet", "success")
    return redirect(url_for("quiz"))


@app.route('/multiplayer_results')
def multiplayer_results():
    if "email" not in session or "multiplayer_game_id" not in session:
        flash("Multiplayer-Session ist abgelaufen.", "danger")
        return redirect(url_for("multiplayer"))

    game = MultiplayerGame.query.filter_by(game_id=session["multiplayer_game_id"]).first()
    if not game:
        flash("Multiplayer-Spiel nicht gefunden.", "danger")
        return redirect(url_for("multiplayer"))

    user = Students.query.filter_by(email=session["email"]).first()
    friend = Students.query.filter_by(email=game.player2 if session["email"] == game.player1 else game.player1).first()

    return render_template("multiplayer_results.html", user=user, friend=friend, game=game)











@app.route('/add_course', methods=['POST'])
def add_course():
    course_name = request.form.get('course_name').strip()

    if course_name:
        new_course = Course(name=course_name)  # Course sınıfını doğru kullanın
        db.session.add(new_course)
        db.session.commit()
        flash('Kurs erfolgreich hinzugefügt', 'success')
    
    return redirect(url_for('fragenkatalog'))


@app.route('/calculate_score', methods=['POST'])
def calculate_score():
    if "email" not in session:
        return jsonify({"error": "Bitte loggen Sie sich ein."}), 403

    total_score = 0

    for key, value in request.form.items():
        if key.startswith("question_"):  
            question_id = int(key.split("_")[1])
            selected_answer = int(value)

            question = Questions.query.get(question_id)
            if question and question.correct_answer == selected_answer:
                total_score += 5  

    return jsonify({"total_score": total_score})


@app.route('/fragenkatalog', methods=['GET', 'POST'])
def fragenkatalog():

    if "email" not in session:  # Kullanıcı giriş yapmamışsa
        flash("Bitte loggen Sie sich ein, um Fragen hinzuzufügen.", "warning")
        return redirect(url_for("login"))  # Login sayfasına yönlendir

    if request.method == 'POST':
        # Form data for the question
        question_text = request.form.get("question").strip()
        answer1 = request.form.get("answer1").strip()
        answer2 = request.form.get("answer2").strip()
        answer3 = request.form.get("answer3").strip()
        answer4 = request.form.get("answer4").strip()
        correct_answer = int(request.form.get("correct-answer"))
        erklaerung_text = request.form.get("erklaerung", "").strip()
        
        # Retrieve the course_id from the form
        course_id = request.form.get("course_id")

        # Find the student who is logged in
        student = Students.query.filter_by(email=session["email"]).first()

        if not student:
            flash("Fehler: Benutzer nicht gefunden!", "danger")
            return redirect(url_for("fragenkatalog"))

        # Create the new question
        new_question = Questions(
    question=question_text,
    answeroption1=answer1,
    answeroption2=answer2,
    answeroption3=answer3,
    answeroption4=answer4,
    erklaerung=erklaerung_text,
    correct_answer=correct_answer,  # ✅ Doğru cevap eklendi
    course_id=course_id,  
    student_id=student.id  
)
        

        db.session.add(new_question)
        db.session.commit()
        flash("Frage erfolgreich hinzugefügt!", "success")

        return redirect(url_for("fragenkatalog"))

    # Fetch all questions along with the course and student details
    questions = Questions.query.join(Course).join(Students).add_columns(
        Questions.id, Questions.question, Questions.answeroption1, Questions.answeroption2,
        Questions.answeroption3, Questions.answeroption4, Questions.erklaerung,
        Course.name.label("course_name"),
        Students.id.label("student_id"), Students.name.label("student_name")
    ).all()

    courses = Course.query.all()  # Get all courses to display in the form
    return render_template('fragenkatalog.html', questions=questions, courses=courses)




@app.route('/edit_question/<int:id>', methods=['GET', 'POST'])
def edit_question(id):
    if "email" not in session:
        flash("Bitte loggen Sie sich ein.", "danger")
        return redirect(url_for("login"))

    question = Questions.query.get_or_404(id)

    if request.method == 'POST':
        question.question = request.form.get("question").strip()
        question.answeroption1 = request.form.get("answer1").strip()
        question.answeroption2 = request.form.get("answer2").strip()
        question.answeroption3 = request.form.get("answer3").strip()
        question.answeroption4 = request.form.get("answer4").strip()
        question.erklaerung = request.form.get("erklaerung").strip()

        # Get the updated course_id from the form
        course_id = request.form.get("course_id")
        question.course_id = course_id  # Update the course_id for the question

        db.session.commit()
        flash("Frage erfolgreich aktualisiert!", "success")
        return redirect(url_for("fragenkatalog"))

    # Fetch available courses to display in the edit form
    courses = Course.query.all()
    return render_template('edit_question.html', question=question, courses=courses)


@app.route('/delete_question/<int:id>', methods=['POST'])
def delete_question(id):
    if "email" not in session:
        flash("Bitte loggen Sie sich ein.", "danger")
        return redirect(url_for("login"))

    question = Questions.query.get_or_404(id)
    db.session.delete(question)
    db.session.commit()
    flash("Frage erfolgreich gelöscht!", "success")

    return redirect(url_for("fragenkatalog"))







@app.route('/leaderboard')
def leaderboard():
    return render_template('leaderboard.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

@app.route('/logout')
def logout():
    session.pop("email", None)
    session.pop("username", None)
    flash('Sie sind abgemeldet!', 'success')  # Çıkış mesajı
    return redirect(url_for('index'))




@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()

        if not name or not email or not password:
            flash('Alle Felder sind erforderlich!', 'danger')
            return render_template('register.html', message='All fields are required')
        
        if not re.match(r'^[a-zA-Z0-9._%+-]+@iu-study\.org$', email):
            flash('Nur E-Mails mit @iu-study.org sind erlaubt!', 'danger')
            return render_template('register.html')

        search = Students.query.filter_by(email=email).first()
        if search is not None:
            flash('E-Mail-Adresse existiert bereits!', 'danger')
            return render_template('register.html', message='Email already exists')

        new_student = Students(name=name, email=email, password=password)
        db.session.add(new_student)
        db.session.commit()

        flash('Registrierung erfolgreich! Bitte loggen Sie sich ein.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if "email" in session:  # Kullanıcı zaten giriş yaptıysa anasayfaya yönlendir
        return redirect(url_for('index'))
    
        return redirect(url_for("login"))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        search = Students.query.filter_by(email=email).first()  # Veritabanında e-maili ara

        if search and search.password == password:  # Kullanıcı bulundu ve şifre doğru
            session["email"] = email  # Oturumu başlat
            session["username"] = search.name  # Kullanıcının adını da saklayalım
            
            return redirect(url_for('index'))
        else:
            flash('Falsche E-Mail oder Passwort!', 'danger')
    
    return render_template('login.html')  # GET isteğinde login sayfasını göster




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 📌 Önce veritabanını oluşturuyoruz

        # 📌 Eğer hiç kurs yoksa, başlangıçta 3 tane ekleyelim
        if not Course.query.first():
            course1 = Course(name="Mathematik")
            course2 = Course(name="Informatik")
            course3 = Course(name="Physik")
            db.session.add_all([course1, course2, course3])
            db.session.commit()
            print("Kurse hinzugefügt")

    app.run(debug=True)  # Sunucuyu başlat

    

 
 
    app.run(debug=True)