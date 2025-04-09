<h1 align="center">개인정보 활용동의 데이터 관리 소프트웨어</h1>

## 🔔 Updates
- `XXXX/XX/XX`: 

<br>
<details>
  <summary>
  <font size="+1">개요</font>
  </summary>
본 소프트웨어는은 (1) 전신 비식별화, (2) 데이터 증강, (3) 개인식별위험도 및 비식별성 평가를 위한 세 개의 모듈로 구성됨. (1) 전신 비식별화 모듈은 자율주행데이터 특성을 고려하여 PNG 파일 포맷의 입력에서 검출된 보행자의 의류와 체형을 변환하여 비식별화 처리함. (2) 데이터 증강 모듈은 PNG 파일 포맷 입력 영상의 날씨, 시간, 계절 특성을 바꾼 가짜 이미지를 생성하여 데이터를 증강함. (3) 개인식별위험도 및 비식별성 평가 모듈은 PNG 파일 포맷의 입력에서 개인정보(얼굴, 번호판)가 식별될 위험성과 비식별 처리 후 개인정보의 식별 가능성을 평가함. 본 연구의 결과물은 자율주행데이터 비식별화 및 증강에 사용될 수 있으며, 비식별화에 대한 AI 데이터 가치 보존율 검증에 활용 가능함
</details>

## 소개
본 레포지토리는 과학기술정보통신부 및 정보통신기획평가원의 정보통신·방송 연구개발사업의 일환으로 수행한 '자율주행용 수집/활용 데이터에 대한 개인정보처리 기술 개발(과제번호 : 2021-0-01062)' 연구과제의 산출물인 공개 SW인 개인정보 활용동의 데이터 관리 소프트웨어이다.

## 🔥 사용방법
### 1. 코드준비 및 환경설정 🔧
```bash
git clone https://github.com/junha425/KITECH_DMP
cd KITECH_DMP

# create env using conda
conda create -n KITECH_DMP python==3.10.12
conda activate KITECH_DMP
# install dependencies with pip
pip install -r requirements.txt
```
### 2. 모델 체크포인트 다운로드
```bash
# first, ensure git-lfs is installed, see: https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage
git lfs install
# clone the weights
Coming soon..
```

### 3. KITECH_DMP 실행 🚀
Before running, ensure you configure the necessary settings through the `app.py` file.


## TODO
- [X] Code
- [ ] Checkpoint

## 연락처
junha@kitech.re.kr / sjyou21@kitech.re.kr
