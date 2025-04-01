import os
import cv2
import zipfile
from datetime import datetime
import logging
import numpy as np
import base64
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

import openai
openai.api_key = 'your_api_key'

from utils.anonymizer import Anonymizer
from utils.dataAug import DataAugmentation
from utils.dataAug_ import DataAugmentation_
from utils.fullbody import FullBodyAnonymizer
from utils.deidFunc import image_blurring, image_masking

UPLOAD_FOLDER = os.path.join('static', 'media_files')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'txt', 'xlsx', 'mp4', 'avi', 'mov', 'mp3', 'wav'}
SECRET_KEY = 'your_secret_key'
DATABASE_URI = 'sqlite:///your_database_file.db'

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# db = SQLAlchemy(app)
app.config['SQLALCHEMY_BINDS'] = {
    'risk_db': 'sqlite:///risk_database.db',
    'augmentation_db': 'sqlite:///augmentation_database.db',
    'fullbody_db': 'sqlite:///fullbody_database.db'
}
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = '/login'
login_manager.init_app(app)

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class RiskUploadedFile(db.Model):
    __bind_key__ = 'risk_db'
    __tablename__ = 'uploaded_files_risk'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now)
    consent = db.Column(db.String(20))
    risk_level = db.Column(db.String(20))
    deid_level = db.Column(db.String(20))
    file_size = db.Column(db.Float, nullable=False)
    text_content = db.Column(db.Text)

class AugmentationUploadedFile(db.Model):
    __bind_key__ = 'augmentation_db'
    __tablename__ = 'uploaded_files_augmentation'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now)
    file_size = db.Column(db.Float, nullable=False)
    text_content = db.Column(db.Text)

class FullBodyUploadedFile(db.Model):
    __bind_key__ = 'fullbody_db'
    __tablename__ = 'uploaded_files_fullbody'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now)
    file_size = db.Column(db.Float, nullable=False)
    text_content = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    # 사용자 ID로 사용자 로드
    return User.query.get(int(user_id))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # 사용자 회원가입 처리
    if current_user.is_authenticated:
        return redirect(url_for('risk'))

    if request.method == 'POST':
        username = request.form.get('signup_username')
        password = request.form.get('signup_password')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('이미 존재하는 사용자 이름입니다. 다른 이름을 선택하세요.', 'error')
        else:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('회원 가입이 완료되었습니다. 로그인하세요.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')

@login_manager.unauthorized_handler
def unauthorized():
    # 인증되지 않은 사용자를 로그인 페이지로 리디렉션
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 사용자 로그인 처리
    if current_user.is_authenticated:
        return redirect(url_for('risk'))

    if request.method == 'POST':
        username = request.form.get('login_username')
        password = request.form.get('login_password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            logging.info(f"User '{username}' logged in")
            return redirect(url_for('risk'))
        else:
            flash('로그인에 실패했습니다. 아이디와 패스워드를 확인하세요.', 'error')
            logging.warning(f"Failed login attempt for user '{username}'")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # 사용자 로그아웃 처리
    logout_user()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('risk'))

@app.route('/change_password_page', methods=['GET'])
@login_required
def change_password_page():
    # 비밀번호 변경 페이지
    return render_template('change_password.html')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    # 비밀번호 변경
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not check_password_hash(current_user.password, current_password):
        flash('현재 비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('change_password_page'))

    if new_password != confirm_password:
        flash('새로운 비밀번호와 확인 비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('change_password_page'))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash('비밀번호가 성공적으로 변경되었습니다. 다시 로그인해주세요.', 'success')
    logout_user()
    return redirect(url_for('login'))

def allowed_file(filename):
    # 파일 확장자를 검사하여 허용된 파일인지 확인
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
@login_required
def risk():
    # 데이터 관리
    uploaded_files = RiskUploadedFile.query.all()
    return render_template('risk.html', uploaded_files=uploaded_files)

@app.route('/upload', methods=['POST'])
def upload():
    # 파일 업로드 및 익명화 처리
    anonymizer = Anonymizer(UPLOAD_FOLDER)
    uploaded_filenames = []

    if 'file' in request.files:
        files = request.files.getlist('file')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                consent, risk_level, deid_level, file_size = anonymizer.process_uploaded_file(file)
                uploaded_filenames.append(filename)

                # 파일명이 이미 존재하는지 확인
                uploaded_file = RiskUploadedFile.query.filter_by(filename=filename).first()
                if uploaded_file:
                    # 기존 레코드 업데이트
                    uploaded_file.consent = consent
                    uploaded_file.risk_level = risk_level
                    uploaded_file.deid_level = deid_level
                    uploaded_file.file_size = file_size
                    uploaded_file.upload_time = datetime.now()
                else:
                    # 새로운 레코드 생성
                    uploaded_file = RiskUploadedFile(
                        filename=filename,
                        consent=consent,
                        risk_level=risk_level,
                        deid_level=deid_level,
                        file_size=file_size
                    )
                    db.session.add(uploaded_file)

                db.session.commit()

    if uploaded_filenames and consent is None:
        flash('파일이 업로드되었습니다.')
    elif uploaded_filenames and consent == 'on':
        flash('익명화 요청이 확인되었습니다. 익명화된 파일이 업로드되었습니다.')

    return redirect(url_for('risk'))

@app.route('/download_selected', methods=['POST'])
def download_selected():
    # 선택 파일 다운로드
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('다운로드할 파일을 선택하세요.', 'error')
        return redirect(url_for('risk'))

    zip_filename = 'selected_files.zip'
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for filename in selected_files:
            uploaded_file = RiskUploadedFile.query.filter_by(filename=filename).first()
            if uploaded_file:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                zipf.write(file_path, filename)

    return send_from_directory(app.config['UPLOAD_FOLDER'], zip_filename)

@app.route('/delete_selected', methods=['POST'])
def delete_selected():
    #관리자 권한으로 선택 파일 삭제
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('삭제할 파일을 선택하세요.', 'error')
        return redirect(url_for('risk'))

    if not current_user.is_authenticated or current_user.username != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('risk'))

    success_messages = []
    error_messages = []
    for filename in selected_files:
        uploaded_file = RiskUploadedFile.query.filter_by(filename=filename).first()
        if uploaded_file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(uploaded_file)
            db.session.commit()
            success_messages.append(filename)
        else:
            error_messages.append(filename)

    if success_messages:
        flash(f'파일 {", ".join(success_messages)}이 삭제되었습니다.', 'success')
    if error_messages:
        flash(f'파일 {", ".join(error_messages)}을 찾을 수 없습니다.', 'error')

    return redirect(url_for('risk'))

@app.route('/augmentation')
@login_required
def augmentation():
    # 전신 비식별화
    uploaded_files = AugmentationUploadedFile.query.all()
    return render_template('augmentation.html', uploaded_files=uploaded_files)

@app.route('/augmentation_upload', methods=['POST'])
def augmentation_upload():
    augmentation_method = request.form.get('augmentation_method')

    if augmentation_method in ('day2night', 'clear2rainy'):
        data_augmentation_cls = DataAugmentation
        process_method_name = 'process_uploaded_file'
    elif augmentation_method == 'clear2snowy':
        data_augmentation_cls = DataAugmentation_ 
        process_method_name = 'process_uploaded_file_'
    else:
        flash('지원하지 않는 데이터 증강 방식입니다.')
        return redirect(url_for('augmentation'))

    data_augmentation = data_augmentation_cls(UPLOAD_FOLDER)

    uploaded_filenames = []

    if 'file' in request.files:
        files = request.files.getlist('file')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                uploaded_filenames.append(filename)

                process_func = getattr(data_augmentation, process_method_name)
                file_size = process_func(file)

                uploaded_file = AugmentationUploadedFile(filename=filename, file_size=file_size)
                db.session.add(uploaded_file)
                db.session.commit()

    if uploaded_filenames:
        flash('파일이 업로드되었습니다.')

    return redirect(url_for('augmentation'))


@app.route('/augmentation_download_selected', methods=['POST'])
def augmentation_download_selected():
    # 선택 파일 다운로드
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('다운로드할 파일을 선택하세요.', 'error')
        return redirect(url_for('fullbody'))

    zip_filename = 'selected_files.zip'
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for filename in selected_files:
            uploaded_file = AugmentationUploadedFile.query.filter_by(filename=filename).first()
            if uploaded_file:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                zipf.write(file_path, filename)

    return send_from_directory(app.config['UPLOAD_FOLDER'], zip_filename)

@app.route('/augmentation_delete_selected', methods=['POST'])
def augmentation_delete_selected():
    #관리자 권한으로 선택 파일 삭제
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('삭제할 파일을 선택하세요.', 'error')
        return redirect(url_for('augmentation'))

    if not current_user.is_authenticated or current_user.username != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('augmentation'))

    success_messages = []
    error_messages = []
    for filename in selected_files:
        uploaded_file = AugmentationUploadedFile.query.filter_by(filename=filename).first()
        if uploaded_file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(uploaded_file)
            db.session.commit()
            success_messages.append(filename)
        else:
            error_messages.append(filename)

    if success_messages:
        flash(f'파일 {", ".join(success_messages)}이 삭제되었습니다.', 'success')
    if error_messages:
        flash(f'파일 {", ".join(error_messages)}을 찾을 수 없습니다.', 'error')

    return redirect(url_for('augmentation'))

@app.route('/fullbody')
@login_required
def fullbody():
    # 전신 비식별화
    uploaded_files = FullBodyUploadedFile.query.all()
    return render_template('fullbody.html', uploaded_files=uploaded_files)

@app.route('/fullbody_upload', methods=['POST'])
def fullbody_upload():
    # 스타일 전이용 파일 업로드 및 처리
    fullbody_anonymizer = FullBodyAnonymizer(UPLOAD_FOLDER)
    uploaded_filenames = []

    if 'file' in request.files:
        files = request.files.getlist('file')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                uploaded_filenames.append(filename)

                file_size = fullbody_anonymizer.process_uploaded_file(file)

                uploaded_file = FullBodyUploadedFile(filename=filename, file_size=file_size)
                db.session.add(uploaded_file)
                db.session.commit()

    if uploaded_filenames:
        flash('파일이 업로드되었습니다.')

    return redirect(url_for('fullbody'))

@app.route('/fullbody_capture', methods=['POST'])
def fullbody_capture():
    try:
        data_url = request.form.get('captured_image')
        if not data_url:
            flash("캡처된 이미지가 전달되지 않았습니다.", "error")
            return redirect(url_for('fullbody'))

        header, encoded = data_url.split(',', 1)
        file_ext = '.png'
        if 'image/jpeg' in header:
            file_ext = '.jpg'

        decoded = base64.b64decode(encoded)
        
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + file_ext

        # 1) BytesIO로 감싼 뒤
        decoded_io = BytesIO(decoded)
        decoded_io.seek(0)

        # 2) FileStorage 객체로 래핑
        #    content_type은 필요에 맞춰 설정 (image/png, image/jpeg 등)
        if file_ext == '.jpg':
            content_type = 'image/jpeg'
        else:
            content_type = 'image/png'
        
        file_storage = FileStorage(decoded_io, filename=filename, content_type=content_type)

        # 3) 이제 file_storage는 file.save(...) 등을 지원
        fullbody_anonymizer = FullBodyAnonymizer(app.config['UPLOAD_FOLDER'])
        file_size = fullbody_anonymizer.process_uploaded_file(file_storage)

        # DB에 업로드 정보 기록
        uploaded_file = FullBodyUploadedFile(filename=filename, file_size=file_size)
        db.session.add(uploaded_file)
        db.session.commit()

        flash(f"파일이 업로드 되었습니다: {filename}", "success")
    
    except Exception as e:
        print(e)
        flash("웹캠 이미지 처리 중 오류가 발생했습니다.", "error")
    
    return redirect(url_for('fullbody'))

@app.route('/fullbody_download_selected', methods=['POST'])
def fullbody_download_selected():
    # 선택 파일 다운로드
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('다운로드할 파일을 선택하세요.', 'error')
        return redirect(url_for('fullbody'))

    zip_filename = 'selected_files.zip'
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for filename in selected_files:
            uploaded_file = FullBodyUploadedFile.query.filter_by(filename=filename).first()
            if uploaded_file:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                zipf.write(file_path, filename)

    return send_from_directory(app.config['UPLOAD_FOLDER'], zip_filename)

@app.route('/fullbody_delete_selected', methods=['POST'])
def fullbody_delete_selected():
    #관리자 권한으로 선택 파일 삭제
    selected_files = request.form.getlist('selected_files')

    if not selected_files:
        flash('삭제할 파일을 선택하세요.', 'error')
        return redirect(url_for('fullbody'))

    if not current_user.is_authenticated or current_user.username != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('fullbody'))

    success_messages = []
    error_messages = []
    for filename in selected_files:
        uploaded_file = FullBodyUploadedFile.query.filter_by(filename=filename).first()
        if uploaded_file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(uploaded_file)
            db.session.commit()
            success_messages.append(filename)
        else:
            error_messages.append(filename)

    if success_messages:
        flash(f'파일 {", ".join(success_messages)}이 삭제되었습니다.', 'success')
    if error_messages:
        flash(f'파일 {", ".join(error_messages)}을 찾을 수 없습니다.', 'error')

    return redirect(url_for('fullbody'))

@app.route('/preview/<filename>')
def preview(filename):
    # 포스트프로세싱 이미지 프리뷰
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/postprocessing')
def postprocessing():
    # 포스트프로세싱 페이지
    media_files = os.listdir(app.config['UPLOAD_FOLDER'])

    image_file_list = [file for file in media_files if file.split('.')[-1].lower() in ['png', 'jpg', 'jpeg', 'bmp']]
    text_file_list = [file for file in media_files if file.endswith('.txt')]

    return render_template('postprocessing.html', image_file_list=image_file_list, text_file_list=text_file_list)

@app.route('/save_image', methods=['POST'])
def save_image():
    # 포스트프로세싱된 이미지 저장
    try:
        data = request.get_json()
        image_filename = data['imageFilename']
        annotation_data = data['annotationData']
        image_anonymization_method = data.get('anonymizationMethod')

        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)

        annotated_image = image.copy()

        for annotation in annotation_data:
            x = annotation.get('x')
            y = annotation.get('y')
            width = annotation.get('width')
            height = annotation.get('height')

            start_x = int(x)
            start_y = int(y)
            end_x = int(x + width)
            end_y = int(y + height)

            start_x = max(0, min(start_x, annotated_image.shape[1]))
            end_x = max(0, min(end_x, annotated_image.shape[1]))
            start_y = max(0, min(start_y, annotated_image.shape[0]))
            end_y = max(0, min(end_y, annotated_image.shape[0]))

            ano_roi = annotated_image[start_y:end_y, start_x:end_x]

            if ano_roi.size == 0:
                continue

            mask = np.zeros_like(ano_roi)
            radius_x = int((end_x - start_x) / 2)
            radius_y = int((end_y - start_y) / 2)
            center_coordinates = (radius_x, radius_y)
            axes_lengths = (radius_x, radius_y)
            cv2.ellipse(mask, center_coordinates, axes_lengths, 0, 0, 360, (255, 255, 255), -1)

            if image_anonymization_method == 'blur':
                ano_roi = image_blurring(ano_roi)
            elif image_anonymization_method == 'mask':
                ano_roi = image_masking(ano_roi)

            ano_roi = cv2.bitwise_and(ano_roi, mask)

            annotated_image[start_y:end_y, start_x:end_x] = cv2.bitwise_and(
                annotated_image[start_y:end_y, start_x:end_x], cv2.bitwise_not(mask))
            annotated_image[start_y:end_y, start_x:end_x] = cv2.add(
                annotated_image[start_y:end_y, start_x:end_x], ano_roi)

        cv2.imwrite(image_path, annotated_image)

        return jsonify({'message': '데이터 저장 완료!', 'annotatedImage': image_filename})
    except Exception as e:
        logging.error(f"Error saving image: {e}")
        return jsonify({'message': f'데이터 저장 중 에러 발생: {e}'}), 500


@app.route('/save_text', methods=['POST'])
def save_text():
    # 포스트프로세싱된 텍스트 저장
    try:
        data = request.get_json()
        text_filename = data['textFilename']
        annotation_text = data['textContent']

        annotated_text_path = os.path.join(app.config['UPLOAD_FOLDER'], text_filename)

        file_record = RiskUploadedFile.query.filter_by(filename=text_filename).first()

        if file_record:
            file_record.text_content = annotation_text
            db.session.commit()

            with open(annotated_text_path, 'w', encoding='utf-8') as file:
                file.write(annotation_text)

            return jsonify({'message': '데이터 저장 완료!', 'annotatedText': text_filename})
        else:
            return jsonify({'message': '파일을 찾을 수 없음'}), 404
    except Exception as e:
        logging.error(f"Error saving text: {e}")
        return jsonify({'message': f'데이터 저장 중 에러 발생: {e}'}), 500

# 날짜 형식 필터 추가
@app.template_filter()
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    return value.strftime(format)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
