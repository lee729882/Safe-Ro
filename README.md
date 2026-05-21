# 🌡️ Safe-Ro: Real-time Heatwave Housing Safety Diagnostic System
**2026 Mokpo National University Capstone Design Project**  
기후 재난(폭염/도시열섬) 주거 취약성 종합 안전 진단 대시보드 및 AI 복지 정책 리포트

---

## 📋 1. Project Overview (프로젝트 개요)
Safe-Ro는 심각해지는 기후 변화와 폭염 속에서 주거 취약계층(고령자, 독거노인 등)의 안전을 지키기 위한 지능형 안심 진단 시스템입니다. 기상청 실시간 기후 데이터와 국토교통부 건축물대장, 통계청 인구 데이터를 융합하여 해당 행정동의 **폭염 주거 위험도(Risk Score)**를 0~100점 수치로 시각화하며, LLM 기반의 지자체 맞춤형 AI 폭염 대비 정책 리포트를 자동 생성합니다.

## 🔗 2. Integrated Data Pipeline (데이터 통합 전략)
본 프로젝트는 다양한 형태의 국가 공공데이터 및 통계 데이터를 실시간으로 결합하여 폭염 취약성 분석의 신뢰성을 극대화했습니다.

### 📊 Real-time Data Source
| Category | API Source / Data | Key Insights |
|---|---|---|
| Climate | 기상청 방재기상관측(AWS) API | 해당 지역 최인접 관측소의 여름철 최고 기온, 폭염 일수, 열대야 일수 실시간 분석 |
| Building | 국토교통부 건축HUB 건축물대장 | 건축물 노후도(사용승인일), 지붕 구조, 주건축물 구조 등 주거 환경의 열 취약성 검증 |
| Population | 통계청 KOSIS 데이터 (CSV) | 읍면동 단위 65세 이상 고령자 비율 및 독거노인 밀집도 매칭을 통한 사회적 취약계층 분석 |
| Geospatial | Kakao Maps API & Kostat GeoJSON | 전국 3,500여 개 읍면동 경계 매핑 및 거리 기반 그라데이션 폭염 위험도 히트맵 렌더링 |
| AI / LLM | NVIDIA NIM / OpenAI API | 취약성 지표(기후, 건축, 인구) 기반 지자체용 복지/대피소 확충 AI 리포트 생성 |

## 🖥️ 3. Main Features (핵심 기능)
- **Heatwave Risk Engine**: 폭염 기온(기후), 건축물 노후도(환경), 독거노인 비율(인구)의 3차원 데이터를 가중치 기반으로 종합 분석하여 최종 폭염 위험도를 산출합니다.
- **AI Welfare Policy Report**: 분석된 지역 특성(예: "노후 주택 70% 이상, 독거노인 밀집")을 LLM에 주입하여, 무더위 쉼터 배치, 방문 간호 인력 보충 등 실질적이고 구체적인 행정 정책 리포트를 생성합니다.
- **Interactive Nationwide Heatmap**: 카카오 맵(Kakao Map) 위에 전국 읍면동 폴리곤을 렌더링하고, 선택 지역을 중심으로 거리에 비례하여 위험도가 퍼져나가는 인터랙티브 그라데이션 히트맵을 구현했습니다.
- **Real-time Filter & Dashboard**: UI 슬라이더를 통해 위험도(Risk Filter) 기준에 미달하는 안전 지역을 지도에서 숨기거나, 실시간으로 통계치(인포그래픽)를 확인하는 다이내믹 대시보드를 제공합니다.

## 📂 4. Project Structure (폴더 구조)
```text
Safe-Ro/
├── frontend/               # [Frontend] React + Vite + Tailwind CSS + Kakao Map API
├── venv/                   # [Backend] Python 가상환경
├── app.py                  # [Server] Flask API 및 공공데이터(기상청, 국토부) 병렬 처리 엔진
├── download.py             # [Script] 전국 단위 대용량 GeoJSON 데이터 파싱 및 다운로드 스크립트
├── requirements.txt        # [Python] 의존성 라이브러리 목록 (Flask, Pandas, OpenAI 등)
├── .env                    # [Security] API 키 관리 (Git 제외)
├── .gitignore              # [Git] 불필요한 파일(캐시, 가상환경 등) 제외 설정
└── README.md               # [Docs] 프로젝트 기술 문서
```

## 📂 5. Getting Started (시작하기)
### 🛠️ Step 1. Environment Setup (환경 설정)
```bash
# 가상환경 활성화 및 라이브러리 설치
python -m venv venv
./venv/Scripts/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 🏃 Step 2. Run Application (실행)
먼저 전국 행정동 지형 데이터(GeoJSON)를 준비한 후, 백엔드와 프론트엔드를 각각 실행합니다.

**[GeoJSON 다운로드 및 Backend 실행]**
```bash
# 1. 원본 지도 데이터 다운로드 (최초 1회 필수)
python download.py

# 2. Flask 서버 실행
python app.py
```

**[Frontend 실행]**
```bash
cd frontend
npm install
npm run dev
```
