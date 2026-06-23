# -*- coding: utf-8 -*-
"""
=============================================================
  기후 재난(폭염) 주거 안전 진단 시스템 — Backend API Server
  Domain: 폭염 주거 위험도 분석 + 복지 정책 조언
=============================================================
"""
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests as req_lib
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import re
import pandas as pd
import logging
import hashlib
import traceback
import xmltodict
import math
import json
from requests.adapters import HTTPAdapter
from openai import OpenAI
import shutil

# --- GeoJSON 준비 ---
def prepare_geojson():
    import urllib.request
    dest = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend", "public", "dongs.json"))
    # 파일이 없거나 너무 작으면(잘린 파일) 다시 다운로드
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000000:
        try:
            print("[System] Downloading full GeoJSON file from GitHub...")
            url = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_submunicipalities_geo_simple.json"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            print("[System] GeoJSON file dongs.json has been successfully prepared in public folder.")
        except Exception as ex:
            print("[System] Error preparing GeoJSON:", ex)

prepare_geojson()
# --------------------
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────
# 로깅 설정 (터미널 출력)
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────────────
# 이미지 프록시 (카카오 정적 지도 / 로드뷰)
# ─────────────────────────────────────────────────────────────
@app.route('/api/thumbnail', methods=['GET'])
def thumbnail_proxy():
    """카카오 정적 지도(Static Map) 이미지를 프록시합니다."""
    lat, lng = request.args.get('lat'), request.args.get('lng')
    k_key = os.getenv("KAKAO_API_KEY")
    if not lat or not lng: return "Missing coordinates", 400
    
    url = "https://dapi.kakao.com/v2/maps/staticmap"
    params = {
        "center": f"{lng},{lat}", 
        "level": "3", 
        "size": "400x300", 
        "marker": f"{lng},{lat}"
    }
    headers = {"Authorization": f"KakaoAK {k_key}"} if k_key else {}
    
    try:
        r = req_lib.get(url, params=params, headers=headers, stream=True, timeout=5)
        if r.status_code == 200:
            return Response(r.iter_content(chunk_size=1024), content_type='image/png')
        log.warning(f"[IMAGE-PROXY] Kakao API failed: {r.status_code} for lat={lat}, lng={lng}")
        return "", 404
    except Exception as e:
        log.error(f"[IMAGE-PROXY ERROR] Thumbnail: {e}")
        return "Internal Error", 500

@app.route('/api/roadview', methods=['GET'])
def roadview_proxy():
    """로드뷰 이미지를 프록시합니다."""
    panoid = request.args.get('panoid')
    if not panoid: return "", 404
    
    url = f"https://map2.daumcdn.net/map_roadview/2/11/L0/3/1/{panoid}.jpg"
    try:
        r = req_lib.get(url, stream=True, timeout=5)
        if r.status_code == 200:
            return Response(r.iter_content(chunk_size=1024), content_type='image/jpeg')
        log.warning(f"[IMAGE-PROXY] Roadview failed: {r.status_code} for panoid={panoid}")
    except Exception as e:
        log.error(f"[IMAGE-PROXY ERROR] Roadview: {e}")
    return "", 404


# ─────────────────────────────────────────────────────────────
# CONFIG & API KEYS
# ─────────────────────────────────────────────────────────────
SERVICE_KEY     = os.getenv("PUBLIC_DATA_INCODING_KEY") or os.getenv("PUBLIC_DATA_KEY")
VWORLD_KEY      = os.getenv("VWORLD_KEY")
VWORLD_DOMAIN   = os.getenv("VWORLD_DOMAIN", "http://localhost:5174")
KMA_API_KEY     = os.getenv("KMA_API_KEY", "")          # 기상청 API 키 (선택)
KOSIS_API_KEY   = os.getenv("KOSIS_API_KEY", "")        # 통계청 KOSIS API 키 (선택)
BACKEND_URL     = "http://localhost:5000"

# 전역 캐시 (메모리)
API_CACHE = {}


# ─────────────────────────────────────────────────────────────
# 생활쓰레기 CSV 로드 (서버 시작 시 1회)
# ─────────────────────────────────────────────────────────────
try:
    CSV_PATH = os.path.join(os.path.dirname(__file__), '생활쓰레기배출정보.csv')
    WASTE_DF = pd.read_csv(CSV_PATH, encoding='cp949')
    log.info(f"[CSV] 생활쓰레기 데이터 로드 완료: {len(WASTE_DF)}건")
except Exception as e:
    WASTE_DF = None
    log.warning(f"[CSV] 로드 실패: {e}")

# ── 인구 통계 CSV 로드 (서버 시작 시 1회) ──
try:
    ELDERLY_CSV_PATH = os.path.join(os.path.dirname(__file__), 'pop_elderly.csv')
    POP_ELDERLY_DF = pd.read_csv(ELDERLY_CSV_PATH, encoding='cp949')
    log.info(f"[CSV] pop_elderly 로드 완료: {len(POP_ELDERLY_DF)}건")
except Exception as e:
    POP_ELDERLY_DF = None
    log.warning(f"[CSV] pop_elderly 로드 실패: {e}")

try:
    SOLO_CSV_PATH = os.path.join(os.path.dirname(__file__), 'pop_solo.csv')
    POP_SOLO_DF = pd.read_csv(SOLO_CSV_PATH, encoding='cp949')
    log.info(f"[CSV] pop_solo 로드 완료: {len(POP_SOLO_DF)}건")
except Exception as e:
    POP_SOLO_DF = None
    log.warning(f"[CSV] pop_solo 로드 실패: {e}")


# ── 지오코딩 영구 캐시 시스템 ──
GEO_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'geocoding_cache.json')
GEO_CACHE = {}

def load_geo_cache():
    global GEO_CACHE
    if os.path.exists(GEO_CACHE_PATH):
        try:
            with open(GEO_CACHE_PATH, 'r', encoding='utf-8') as f:
                GEO_CACHE = json.load(f)
            log.info(f"[CACHE] 지오코딩 캐시 로드 완료: {len(GEO_CACHE)}건")
        except Exception as e:
            log.warning(f"[CACHE] 캐시 로드 오류: {e}")
            GEO_CACHE = {}

def save_geo_cache():
    try:
        with open(GEO_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(GEO_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"[CACHE] 캐시 저장 불가: {e}")

load_geo_cache()


# ── NVIDIA NIM / OpenAI 클라이언트 설정 ──
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    timeout=120.0,     # 실측 기준 응답에 76~81초 소요 → 120초로 여유 확보
    max_retries=0      # 자동 재시도 비활성화 (재시도가 더 긴 대기 유발)
)


# ── 카카오 API 전역 세션 (Connection Pool) ──
kakao_session = req_lib.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
kakao_session.mount('http://', adapter)
kakao_session.mount('https://', adapter)
k_api_key = os.getenv("KAKAO_API_KEY")
if k_api_key:
    kakao_session.headers.update({"Authorization": f"KakaoAK {k_api_key}"})


# ─────────────────────────────────────────────────────────────
# 범용 유틸리티 함수
# ─────────────────────────────────────────────────────────────
def format_bunji(s):
    """지번의 본번/부번에서 숫자만 추출하여 4자리(zfill)로 반환"""
    if not s: return '0000'
    nums = re.sub(r'[^0-9]', '', str(s))
    return nums.zfill(4) if nums else '0000'

def normalize_jibun(s):
    """지번 표준화 (예: '015-003' → '15-3')"""
    if not s: return ""
    parts = str(s).split('-')
    normalized = []
    for p in parts:
        try: normalized.append(str(int(p.strip())))
        except: normalized.append(p.strip())
    return '-'.join(normalized)

def clean_text(s):
    """괄호 내용 제거 + 공백 정리"""
    if not s: return ""
    return re.sub(r'\(.*?\)', '', str(s)).strip()

def safe_int(s, default=0):
    """쉼표 포함 문자열 → 정수"""
    try:
        return int(str(s).replace(',', '').strip())
    except:
        return default

def safe_float(s, default=0.0):
    try:
        return float(str(s).strip())
    except:
        return default

def get_distance(lat1, lon1, lat2, lon2):
    """Haversine 공식으로 두 좌표 간의 직선 거리(km)를 구합니다."""
    if not all([lat1, lon1, lat2, lon2]): return 999.0
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# =============================================================
# [1] 국토부 건축물대장 표제부 API — 사용승인일/지붕구조 조회
# =============================================================
def fetch_building_info(sigungu_cd, bjdong_cd, bun, ji):
    """
    국토부 건축물대장 표제부(getBrTitleInfo) + 총괄표제부(getBrRecapTitleInfo)를 호출하여
    폭염 주거 안전 진단에 필요한 핵심 데이터를 추출합니다.
    
    주요 추출 필드:
      - useAprvDe (사용승인일) → 건물 노후도 산출
      - roofCdNm  (지붕구조코드명) → 폭염 취약 지붕 판별
      - strctCdNm (주구조) → 단열 성능 추정
      - mainPurpsCdNm (주용도) → 주거 여부 확인
      
    Returns:
        dict: 건물 정보 객체
    """
    try:
        ENC_KEY  = str(os.getenv("PUBLIC_DATA_INCODING_KEY", "")).strip()
        HUB_BASE = "http://apis.data.go.kr/1613000/BldRgstHubService"
        platGbCd = "1" if ("산" in str(bun) or "산" in str(ji)) else "0"
        bun_fmt  = str(bun).strip().zfill(4)
        ji_fmt   = str(ji).strip().zfill(4)

        def _call(api_name, p_gb, b, j):
            """Raw URL 고정 - requests params/encode 간섭 완전 차단"""
            sep = "&"
            ji_part = f"{sep}ji={j}" if j else ""
            url = (
                f"{HUB_BASE}/{api_name}"
                f"?serviceKey={ENC_KEY}"
                f"{sep}sigunguCd={sigungu_cd}{sep}bjdongCd={bjdong_cd}"
                f"{sep}platGbCd={p_gb}{sep}bun={b}{ji_part}"
                f"{sep}numOfRows=10{sep}pageNo=1{sep}_type=json"
            )
            log.debug(f"[BldRgst] {api_name} platGb={p_gb} bun={b} ji={j}")
            r = req_lib.get(url, timeout=10)
            if r.status_code == 200:
                try:
                    return r.json()
                except: pass
            
            # JSON 파싱 실패 시 XML Fallback
            url_xml = url.replace(f"{sep}_type=json", "")
            rx = req_lib.get(url_xml, timeout=10)
            if rx.status_code == 200:
                return xmltodict.parse(rx.text)
            return None

        def _ext(data):
            """(totalCount, item_list) 추출"""
            if not data:
                return 0, []
            body  = data.get("response", {}).get("body", {})
            total = int(body.get("totalCount", 0) or 0)
            raw   = body.get("items") or {}
            if not isinstance(raw, dict):
                return total, []
            il = raw.get("item") or []
            if isinstance(il, dict):
                il = [il]
            result = il if isinstance(il, list) else []
            return total, result

        # ── 1. 총괄표제부(getBrRecapTitleInfo) 호출 ──
        t8, items8 = _ext(_call("getBrRecapTitleInfo", platGbCd, bun_fmt, ji_fmt))
        if not items8 and ji_fmt != "0000":
            t8, items8 = _ext(_call("getBrRecapTitleInfo", platGbCd, bun_fmt, "0000"))
        
        main_item = items8[0] if items8 else {}
        
        # ── 2. 표제부(getBrTitleInfo) 호출 ──
        t1, items1 = _ext(_call("getBrTitleInfo", platGbCd, bun_fmt, ji_fmt))
        if not items1 and ji_fmt != "0000":
            t1, items1 = _ext(_call("getBrTitleInfo", platGbCd, bun_fmt, "0000"))
            if items1: ji_fmt = "0000"
        
        item = items1[0] if items1 else main_item
        if not item:
            t_f, items_f = _ext(_call("getBrTitleInfo", platGbCd, bun_fmt, ""))
            if items_f: item = items_f[0]

        if not item:
            return {
                "useAprvDe": None, "roofCdNm": "정보 없음",
                "strctCdNm": "정보 없음", "mainPurpsCdNm": "정보 없음",
                "buildAge": None, "grndFlrCnt": None, "ugrndFlrCnt": None,
                "hhldCnt": 0, "totArea": 0,
                "source": "no_data", "msg": "건축물대장 데이터 미조회",
            }

        def _c(v, d="정보 없음"):
            s = str(v).strip() if v is not None else ""
            return s if (s and s not in ("None",)) else d

        # 사용승인일 → 건물 노후도 계산
        use_aprv_de = item.get("useAprvDe")
        build_age = None
        if use_aprv_de and len(str(use_aprv_de)) >= 4:
            try:
                build_year = int(str(use_aprv_de)[:4])
                build_age = datetime.now().year - build_year
            except:
                pass

        # 지붕구조 추출 (roofCdNm)
        roof_cd_nm = _c(item.get("roofCdNm"), "정보 없음")
        # 총괄표제부에 있을 수도 있음
        if roof_cd_nm == "정보 없음" and main_item:
            roof_cd_nm = _c(main_item.get("roofCdNm"), "정보 없음")

        # 세대수
        hhld_cnt = safe_int(item.get("hhldCnt") or item.get("fmlyCnt") or main_item.get("hhldCnt") or 0)
        tot_area = safe_float(item.get("totArea") or main_item.get("totArea") or 0)

        result = {
            "useAprvDe":     use_aprv_de,
            "buildAge":      build_age,
            "buildYear":     int(str(use_aprv_de)[:4]) if use_aprv_de and len(str(use_aprv_de)) >= 4 else None,
            "roofCdNm":      roof_cd_nm,
            "strctCdNm":     _c(item.get("strctCdNm")),
            "mainPurpsCdNm": _c(item.get("mainPurpsCdNm")),
            "grndFlrCnt":    safe_int(item.get("grndFlrCnt")),
            "ugrndFlrCnt":   safe_int(item.get("ugrndFlrCnt")),
            "hhldCnt":       hhld_cnt,
            "totArea":       tot_area,
            "engrEfcRtNm":   _c(item.get("engrEfcRtNm"), "정보 없음"),
            "source":        "molit_building_registry",
            "msg":           "건축물대장 조회 완료",
        }
        log.info(f"[건축물대장] 조회 완료 — 사용승인일={use_aprv_de}, 지붕={roof_cd_nm}, 노후도={build_age}년")
        return result

    except Exception as e:
        log.error(f"[건축물대장] 예외: {e}")
        traceback.print_exc()
        return {
            "useAprvDe": None, "roofCdNm": "정보 없음",
            "strctCdNm": "정보 없음", "mainPurpsCdNm": "정보 없음",
            "buildAge": None, "source": "error", "msg": str(e),
        }


# =============================================================
# [2] 기상청 방재기상관측(AWS) API — 일 최고기온 / 폭염 일수
# =============================================================

# 주요 도시별 AWS 관측소 코드 매핑
AWS_STATION_MAP = {
    "서울": 108, "부산": 159, "대구": 143, "인천": 112, "광주": 156,
    "대전": 133, "울산": 152, "세종": 129, "수원": 119, "춘천": 101,
    "강릉": 105, "청주": 131, "전주": 146, "포항": 138, "제주": 184,
    "창원": 155, "천안": 232, "김해": 253, "구미": 279, "원주": 114,
    "익산": 244, "목포": 165, "여수": 168, "순천": 174, "안동": 136,
}

# 지역명 → 관측소 코드 추출 (시/구/동 중 시 레벨 매칭)
# 지역명 → 관측소 코드 추출 (더 이상 사용하지 않지만 하위 호환성을 위해 유지하거나 제거 가능, 새 로직은 함수 내부 포함)
def fetch_heatwave_data(region_name, time_range="2025 July"):
    """
    기상청 API Hub를 호출하여 특정 지역의 '일 최고기온'과 '폭염 일수'를 가져옵니다.
    응답 형식(Text)을 파싱하여 여름(6~9월) 또는 지정된 시간 범위의 데이터를 추출합니다.
    """
    # 1. 파일 상단의 AWS_STATION_MAP을 사용하여 region_name에 매칭되는 관측소 코드 탐색
    stn_id = 129  # 기본값: 세종(129)
    for key, val in AWS_STATION_MAP.items():
        if key in region_name:
            stn_id = val
            break

    # 2. 기상청 API 호출 설정
    if KMA_API_KEY:
        try:
            if time_range == "2024 July":
                tm1, tm2 = "20240701", "20240731"
            elif time_range == "2024 August":
                tm1, tm2 = "20240801", "20240831"
            elif time_range == "2025 July":
                tm1, tm2 = "20250701", "20250731"
            elif time_range == "2025 August":
                tm1, tm2 = "20250801", "20250831"
            else:
                tm1, tm2 = "20250601", "20250930"

            url = "https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php"
            params = {
                "tm1": tm1,
                "tm2": tm2,
                "obs": "ta_max",
                "stn": stn_id,
                "help": "0",
                "authKey": KMA_API_KEY
            }
            
            r = req_lib.get(url, params=params, timeout=10)
            if r.status_code == 200:
                max_temp = -999.0
                heatwave_days = 0
                
                # 3. 응답(Text) 파싱 로직
                lines = r.text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            # 텍스트 포맷: 시간, 지점, 값 ...
                            val = float(parts[2])
                            if val > max_temp:
                                max_temp = val
                            if val >= 33.0:
                                heatwave_days += 1
                        except ValueError:
                            pass
                
                if max_temp != -999.0:
                    log.info(f"[기상청] 실데이터 조회 완료 — 최고기온={max_temp}℃, 폭염일수={heatwave_days}일")
                    return {
                        "max_temp": max_temp,
                        "heatwave_days": heatwave_days,
                        "avg_summer_temp": 26.5,  # 더미값 유지
                        "tropical_nights": 0,     # 더미값 유지
                        "station_id": stn_id,
                        "source": "kma_api",
                    }
        except Exception as e:
            log.warning(f"[기상청] API 호출 실패 또는 파싱 오류, 더미 데이터 사용: {e}")
            
    # 4. Fallback (더미 데이터)
    seed = int(hashlib.md5(region_name.encode()).hexdigest(), 16) % 100
    base_max = 35.0 + (seed % 20) / 10
    base_heatwave = 10 + (seed % 10)
    
    result = {
        "max_temp": round(base_max, 1),
        "heatwave_days": base_heatwave,
        "avg_summer_temp": round(26.0 + (seed % 30) / 10, 1),
        "tropical_nights": 5 + (seed % 10),
        "station_id": stn_id,
        "source": "dummy",
    }
    log.info(f"[기상청-더미] {region_name} → 최고기온={result['max_temp']}℃, 폭염={result['heatwave_days']}일")
    return result


# =============================================================
# [3] 통계청/행안부 인구 데이터 — 고령자 비율 / 독거가구
# =============================================================

# 주요 시/군/구 고령화율 시뮬레이션 매핑 (2024 행안부 주민등록 통계 근사)
ELDERLY_RATIO_MAP = {
    # 서울
    "강남구": 14.2, "서초구": 14.8, "송파구": 13.5, "강동구": 14.1,
    "마포구": 15.3, "영등포구": 16.8, "종로구": 20.5, "중구": 19.2,
    "용산구": 18.5, "성동구": 15.7, "광진구": 14.9, "동대문구": 18.1,
    "중랑구": 18.9, "성북구": 17.4, "강북구": 22.1, "도봉구": 20.3,
    "노원구": 18.6, "은평구": 19.8, "서대문구": 18.2, "양천구": 15.2,
    "강서구": 15.8, "구로구": 16.4, "금천구": 16.1, "동작구": 16.9,
    "관악구": 16.5,
    # 광역시
    "부산": 21.5, "대구": 18.2, "인천": 14.8, "광주": 15.1,
    "대전": 15.9, "울산": 13.8, "세종": 10.2,
    # 고령지역
    "의성군": 42.1, "고성군": 38.5, "합천군": 40.2, "군위군": 41.8,
    "청도군": 36.7, "영양군": 39.2, "남해군": 37.1,
}

def fetch_population_data(region_name):
    """
    통계청/행안부 인구 데이터를 호출하여
    65세 이상 인구 비율과 독거가구 비율을 가져옵니다.
    
    실제 CSV 파일 조회를 우선 수행하며, 조회 실패 시 더미 데이터로 Fallback합니다.
    """
    # ── 1. 로컬 CSV 파일에서 데이터 조회 시도 ──
    try:
        if POP_ELDERLY_DF is not None and POP_SOLO_DF is not None:
            # 고령자 데이터 추출 (pop_elderly.csv)
            elderly_match = POP_ELDERLY_DF[POP_ELDERLY_DF['행정구역'].str.contains(region_name, na=False, regex=False)]
            # 1인가구 데이터 추출 (pop_solo.csv)
            solo_match = POP_SOLO_DF[POP_SOLO_DF['행정구역'].str.contains(region_name, na=False, regex=False)]
            
            if not solo_match.empty and not elderly_match.empty:
                solo_row = solo_match.iloc[0]
                elderly_row = elderly_match.iloc[0]
                
                # 고령자 CSV(pop_elderly.csv) 처리
                total_pop_col = [c for c in elderly_row.index if '총인구수' in c.replace(' ', '')]
                if total_pop_col:
                    total_pop = safe_int(elderly_row[total_pop_col[0]])
                    
                    # 65세 이상 인구 합산 로직 (다양한 포맷 대응)
                    elderly_sum = 0
                    exact_65_plus = [c for c in elderly_row.index if '65세이상' in c.replace(' ', '') and not ('_남' in c or '_여' in c)]
                    if exact_65_plus:
                        elderly_sum = safe_int(elderly_row[exact_65_plus[0]])
                    else:
                        # 분할 합산 시도
                        added_any = False
                        for age_str in ['65~', '70~', '75~', '80~', '85~', '90~', '95~', '100세']:
                            c_matches = [c for c in elderly_row.index if age_str in c and not ('_남' in c or '_여' in c)]
                            if c_matches:
                                elderly_sum += safe_int(elderly_row[c_matches[0]])
                                added_any = True
                                
                        if not added_any:
                            # 10세 단위 포맷 (60~69세, 70~79세 등) 대응
                            age_60_69_col = [c for c in elderly_row.index if '60~69' in c and not ('_남' in c or '_여' in c)]
                            pop_60_69 = safe_int(elderly_row[age_60_69_col[0]]) if age_60_69_col else 0
                            elderly_sum = pop_60_69 // 2  # 65~69세 절반 추정
                            for age_str in ['70~', '80~', '90~', '100세']:
                                c_matches = [c for c in elderly_row.index if age_str in c and not ('_남' in c or '_여' in c)]
                                if c_matches:
                                    elderly_sum += safe_int(elderly_row[c_matches[0]])
                    
                    elderly_ratio = round((elderly_sum / total_pop) * 100, 1) if total_pop > 0 else 0.0
                else:
                    raise Exception("고령자 CSV에서 '총인구수' 컬럼을 찾을 수 없습니다.")
                
                # 1인가구 CSV(pop_solo.csv) 처리
                total_hh_col = [c for c in solo_row.index if '전체세대' in c or '총세대수' in c or '전체세대수' in c.replace(' ', '')]
                solo_hh_col = [c for c in solo_row.index if '1인세대' in c]
                
                if total_hh_col and solo_hh_col:
                    total_hh = safe_int(solo_row[total_hh_col[0]])
                    solo_hh = safe_int(solo_row[solo_hh_col[0]])
                    solo_ratio = round((solo_hh / total_hh) * 100, 1) if total_hh > 0 else 0.0
                else:
                    raise Exception("1인가구 CSV에서 '전체세대' 또는 '1인세대' 컬럼을 찾을 수 없습니다.")
                
                log.info(f"[인구-CSV] {region_name} → 고령화율={elderly_ratio}%, 독거노인={solo_ratio}%")
                return {
                    "elderly_ratio": elderly_ratio,
                    "solo_elderly_ratio": solo_ratio,
                    "total_population": total_pop,
                    "elderly_population": elderly_sum,
                    "source": "csv",
                }
    except Exception as e:
        log.warning(f"[인구-CSV] 로컬 데이터 처리 오류: {e}. Fallback으로 진행합니다.")

    # ── 2. 더미 데이터 Fallback (실제 통계 근사) ──
    seed = int(hashlib.md5(region_name.encode()).hexdigest(), 16) % 100
    
    elderly_ratio = None
    for area, ratio in ELDERLY_RATIO_MAP.items():
        if area in region_name:
            elderly_ratio = ratio
            break
    
    if elderly_ratio is None:
        elderly_ratio = 18.5 + (seed % 100) / 10 - 5
        elderly_ratio = round(max(10.0, min(45.0, elderly_ratio)), 1)
    
    solo_ratio = round(elderly_ratio * (0.30 + (seed % 10) / 100), 1)
    total_pop = 150000 + (seed * 3000)
    elderly_pop = int(total_pop * elderly_ratio / 100)
    
    result = {
        "elderly_ratio": elderly_ratio,
        "solo_elderly_ratio": solo_ratio,
        "total_population": total_pop,
        "elderly_population": elderly_pop,
        "source": "dummy",
    }
    log.info(f"[인구-더미] {region_name} → 고령화율={elderly_ratio}%, 독거노인={solo_ratio}%")
    return result


# =============================================================
# [4] 데이터 융합 — 폭염 주거 위험도 지수 산출
# =============================================================
def calculate_heatwave_risk_index(building_age, elderly_ratio, max_temp, 
                                   heatwave_days, roof_type="정보 없음",
                                   solo_elderly_ratio=0, tropical_nights=0,
                                   structure_type="정보 없음"):
    """
    폭염 주거 위험도 지수 (0~100)를 산출합니다.
    
    ■ 가중치 구성
      - 노후도 점수 (40%): 건축 연식 기반 감쇄 평가
      - 고령자 비율 점수 (40%): 65세 이상 + 독거노인 비율
      - 기온 점수 (20%): 일 최고기온 + 폭염 일수
    
    ■ 보정 요소
      - 지붕구조: 슬레이트/판넬 등 취약 구조 시 가산
      - 열대야: 열대야 일수에 따른 미세 보정
    
    Args:
        building_age (int/None): 건물 연식 (년)
        elderly_ratio (float): 65세 이상 인구 비율 (%)
        max_temp (float): 일 최고기온 (℃)
        heatwave_days (int): 연간 폭염 일수
        roof_type (str): 지붕구조 코드명
        solo_elderly_ratio (float): 독거노인 비율 (%)
        tropical_nights (int): 열대야 일수
        structure_type (str): 주구조 코드명
        
    Returns:
        dict: 위험도 지수 및 세부 점수
    """
    # ── 1. 노후도 점수 (0~100, 높을수록 위험) ──
    if building_age is None:
        age_risk = 50  # 정보 없음 → 중간값
    elif building_age <= 5:
        age_risk = 10
    elif building_age <= 10:
        age_risk = 20
    elif building_age <= 15:
        age_risk = 35
    elif building_age <= 20:
        age_risk = 50
    elif building_age <= 30:
        age_risk = 70
    elif building_age <= 40:
        age_risk = 85
    else:
        age_risk = 95
    
    # 지붕구조 보정 (슬레이트, 판넬 등 취약 구조)
    roof_bonus = 0
    vulnerable_roofs = ["슬레이트", "판넬", "기와", "목재", "아스팔트싱글", "샌드위치판넬"]
    good_roofs = ["철근콘크리트", "콘크리트", "평슬래브"]
    
    for vr in vulnerable_roofs:
        if vr in roof_type:
            roof_bonus = 10
            break
    for gr in good_roofs:
        if gr in roof_type:
            roof_bonus = -5
            break
    
    age_risk = min(100, max(0, age_risk + roof_bonus))
    
    # ── 2. 고령자 비율 점수 (0~100, 높을수록 위험) ──
    if elderly_ratio <= 10:
        elderly_risk = 15
    elif elderly_ratio <= 15:
        elderly_risk = 30
    elif elderly_ratio <= 20:
        elderly_risk = 50
    elif elderly_ratio <= 25:
        elderly_risk = 65
    elif elderly_ratio <= 30:
        elderly_risk = 80
    elif elderly_ratio <= 35:
        elderly_risk = 90
    else:
        elderly_risk = 95
    
    # 독거노인 비율 보정
    if solo_elderly_ratio > 10:
        elderly_risk = min(100, elderly_risk + 8)
    elif solo_elderly_ratio > 7:
        elderly_risk = min(100, elderly_risk + 5)
    
    # ── 3. 기온 점수 (0~100, 높을수록 위험) ──
    # 최고기온 기반 (33℃ 기준)
    if max_temp <= 30:
        temp_risk = 10
    elif max_temp <= 33:
        temp_risk = 30
    elif max_temp <= 35:
        temp_risk = 50
    elif max_temp <= 37:
        temp_risk = 70
    elif max_temp <= 39:
        temp_risk = 85
    else:
        temp_risk = 95
    
    # 폭염 일수 보정
    if heatwave_days >= 25:
        temp_risk = min(100, temp_risk + 15)
    elif heatwave_days >= 15:
        temp_risk = min(100, temp_risk + 10)
    elif heatwave_days >= 10:
        temp_risk = min(100, temp_risk + 5)
    
    # 열대야 보정
    if tropical_nights >= 20:
        temp_risk = min(100, temp_risk + 5)
    
    # ── 4. 종합 위험도 지수 (가중 평균) ──
    risk_index = round(age_risk * 0.40 + elderly_risk * 0.40 + temp_risk * 0.20)
    risk_index = min(100, max(0, risk_index))
    
    # 위험 등급 판정
    if risk_index >= 80:
        risk_level = "매우 높음"
        risk_color = "#FF1744"
        risk_emoji = "🔴"
    elif risk_index >= 60:
        risk_level = "높음"
        risk_color = "#FF9100"
        risk_emoji = "🟠"
    elif risk_index >= 40:
        risk_level = "보통"
        risk_color = "#FFD600"
        risk_emoji = "🟡"
    elif risk_index >= 20:
        risk_level = "낮음"
        risk_color = "#00E676"
        risk_emoji = "🟢"
    else:
        risk_level = "매우 낮음"
        risk_color = "#2979FF"
        risk_emoji = "🔵"
    
    return {
        "riskIndex":     risk_index,
        "riskLevel":     risk_level,
        "riskColor":     risk_color,
        "riskEmoji":     risk_emoji,
        "ageRisk":       age_risk,
        "elderlyRisk":   elderly_risk,
        "tempRisk":      temp_risk,
        "roofBonus":     roof_bonus,
        "weights": {
            "aging": 0.40,
            "elderly": 0.40,
            "temperature": 0.20,
        },
        "radar": [
            {"subject": "건물노후도", "score": age_risk},
            {"subject": "고령자비율", "score": elderly_risk},
            {"subject": "폭염강도",   "score": temp_risk},
            {"subject": "지붕취약성", "score": min(100, max(0, 50 + roof_bonus * 5))},
            {"subject": "열대야",     "score": min(100, tropical_nights * 4)},
        ],
    }


# =============================================================
# [5] AI 기후 재난/복지 정책 리포트 생성 API
# =============================================================
@app.route('/api/ai-report', methods=['POST'])
def generate_ai_report():
    """
    폭염 주거 위험도 데이터를 기반으로 LLM을 사용하여
    기후 재난 복지 정책 조언 리포트를 생성합니다.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    region_name     = data.get('region_name', '해당 지역')
    risk_index      = data.get('risk_index', 0)
    risk_level      = data.get('risk_level', '보통')
    building_age    = data.get('building_age', '정보 없음')
    roof_type       = data.get('roof_type', '정보 없음')
    elderly_ratio   = data.get('elderly_ratio', 0)
    solo_elderly    = data.get('solo_elderly_ratio', 0)
    max_temp        = data.get('max_temp', 0)
    heatwave_days   = data.get('heatwave_days', 0)
    tropical_nights = data.get('tropical_nights', 0)

    log.info(f"[AI-REPORT] 기후재난 리포트 요청 — 지역: {region_name}, 위험도: {risk_index}")

    prompt = f"""
기후 재난 대응 및 주거 복지 정책 전문 조언자로서, 다음 데이터를 분석하여 정밀 진단 리포트를 작성하세요.
반드시 아래 3단계 형식을 엄격히 준수해야 합니다.

### 1. 🌡️ 현재 주거 취약성 진단
- 지역명: {region_name}
- 폭염 주거 위험도 지수: {risk_index}점 (등급: {risk_level})
- 건물 노후도: {building_age}년 / 지붕구조: {roof_type}
- 여름 최고기온: {max_temp}℃ / 폭염일수: {heatwave_days}일 / 열대야: {tropical_nights}일
이 데이터를 근거로 해당 지역의 폭염 주거 취약성을 종합 진단하세요.
특히 노후 건축물의 단열 성능 저하와 지붕 복사열 문제를 구체적으로 언급하세요.

### 2. 🛡️ 우선 보호 대상 파악
- 고령자(65세 이상) 비율: {elderly_ratio}%
- 독거노인 비율: {solo_elderly}%
고령자, 독거노인, 기저질환자 등 폭염 취약계층을 우선 보호 대상으로 식별하고,
특히 독거노인 가구의 열사병·온열질환 위험을 구체적으로 경고하세요.

### 3. 🏗️ 지자체 맞춤형 복지 정책 제안
위 진단 결과를 바탕으로 실행 가능한 지자체 정책을 최소 5가지 이상 제안하세요.
반드시 다음 카테고리를 포함해야 합니다:
- **건축물 개선**: 쿨루프(Cool Roof) 시공, 차열 도료, 옥상 녹화, 단열재 보강 등
- **복지 서비스**: 방문 간호, 무더위쉼터 확충, 에어컨 보급, 안부 확인 시스템 등
- **도시 인프라**: 그늘막 설치, 쿨링포그, 공원 확충, 바람길 조성 등
각 정책에 대해 예상 효과와 우선순위를 명시하세요.

[분석 데이터]
- 지역: {region_name}
- 폭염 위험도: {risk_index}/100 ({risk_level})
- 건축물 연식: {building_age}년
- 지붕구조: {roof_type}
- 여름 최고기온: {max_temp}℃
- 폭염일수: {heatwave_days}일
- 열대야일수: {tropical_nights}일
- 고령자 비율: {elderly_ratio}%
- 독거노인 비율: {solo_elderly}%

결과는 반드시 Markdown 형식으로, 위 3단계 구조를 지켜서 출력하세요. 불필요한 서론이나 결론은 생략하세요.
"""

    try:
        completion = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",  # 3.1보다 ~5초 빠름 (실측: 76s vs 81s)
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 기후 재난 대응 및 주거 복지 정책 전문 조언자입니다. "
                        "지역별 폭염 주거 취약성 데이터를 분석하여 지자체 맞춤형 정책을 제안합니다. "
                        "결과는 반드시 마크다운 형식으로, 군더더기 없이 전문적으로 제공하세요. "
                        "구체적인 수치와 근거를 들어 설명하며, 실행 가능한 정책을 우선순위와 함께 제시합니다."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1500,
            top_p=1
        )
        report = completion.choices[0].message.content
        return jsonify({"report": report})
    except Exception as e:
        log.error(f"[AI-REPORT ERROR] {e}")
        # 504/타임아웃 에러는 재시도 없이 즉시 503 반환하여 프론트엔드가 빠르게 오류 표시
        err_str = str(e)
        if "504" in err_str or "timeout" in err_str.lower() or "timed out" in err_str.lower():
            return jsonify({"error": "AI 서버 응답 지연 (최대 2분 소요). 잠시 후 다시 시도해 주세요."}), 503
        return jsonify({"error": err_str}), 500


# =============================================================
# [6] 종합 분석 엔드포인트 — /api/heatwave-analyze
# =============================================================
@app.route('/api/heatwave-analyze', methods=['POST'])
def heatwave_analyze():
    """
    폭염 주거 안전 종합 진단 API.
    
    프론트엔드에서 지역 정보를 보내면:
      1. 건축물대장 → 노후도/지붕구조
      2. 기상청 → 기온/폭염 일수
      3. 통계청 → 고령자/독거가구 비율
      4. calculate_heatwave_risk_index() → 위험도 지수 산출
      5. 종합 결과 JSON 반환
    """
    # bun 파싱 실패(0000) 시 region_name 기반 fallback 주소
    DONG_FALLBACK_BUN = {
        "어진동": {"bun":  "0664", "ji": "0000"},
    }
    try:
        data        = request.json
        bjd_code    = data.get('code', '')
        sigungu_cd  = bjd_code[:5] if len(bjd_code) >= 5 else ''
        bjdong_cd   = bjd_code[5:10] if len(bjd_code) >= 10 else ''
        
        target_bun  = format_bunji(data.get('bun', '0'))
        target_ji   = format_bunji(data.get('ji', '0'))
        lat         = float(data.get('lat', 37.5))
        lng         = float(data.get('lng', 127.0))
        region_name = data.get('regionName', '서울')
        time_range  = data.get('timeRange', '2025 July')

        # bun이 "0000"일 때 region_name 기반 fallback 적용
        if target_bun == "0000":
            for key, val in DONG_FALLBACK_BUN.items():
                if key in region_name:
                    target_bun = val["bun"]
                    target_ji  = val["ji"]
                    log.info(f"[/heatwave-analyze] fallback bun 적용 ({key}) bun={target_bun} ji={target_ji}")
                    break

        log.info(f"[/heatwave-analyze] 시작 | 지역={region_name} 코드={bjd_code} bun={target_bun} ji={target_ji}")

        # ── 병렬 데이터 수집 ──
        with ThreadPoolExecutor(max_workers=3) as ex:
            bldg_f = ex.submit(fetch_building_info, sigungu_cd, bjdong_cd, target_bun, target_ji)
            heat_f = ex.submit(fetch_heatwave_data, region_name, time_range)
            pop_f  = ex.submit(fetch_population_data, region_name)
            
            building = bldg_f.result()
            climate  = heat_f.result()
            population = pop_f.result()

        # ── 위험도 지수 산출 ──
        risk = calculate_heatwave_risk_index(
            building_age       = building.get("buildAge"),
            elderly_ratio      = population.get("elderly_ratio", 18.0),
            max_temp           = climate.get("max_temp", 35.0),
            heatwave_days      = climate.get("heatwave_days", 10),
            roof_type          = building.get("roofCdNm", "정보 없음"),
            solo_elderly_ratio = population.get("solo_elderly_ratio", 5.0),
            tropical_nights    = climate.get("tropical_nights", 10),
            structure_type     = building.get("strctCdNm", "정보 없음"),
        )

        # ── 노후도 진단 텍스트 ──
        build_age = building.get("buildAge")
        if build_age is None:
            age_diag = "건축물대장 데이터 미조회로 정확한 노후도 판단이 어렵습니다."
        elif build_age <= 5:
            age_diag = f"준공 {build_age}년 이내 신축 건물 — 단열·방수 성능 최우수"
        elif build_age <= 15:
            age_diag = f"준공 {build_age}년 — 단열 성능 양호, 정기 점검 권장"
        elif build_age <= 25:
            age_diag = f"준공 {build_age}년 — 단열재 노화 가능성, 여름철 실내 온도 상승 주의"
        elif build_age <= 35:
            age_diag = f"준공 {build_age}년 — 노후 건축물로 단열·방수 성능 저하 우려, 리모델링 권장"
        else:
            age_diag = f"준공 {build_age}년 이상 — 심각한 노후화, 폭염 시 실내 온도 급상승 위험, 긴급 단열 보강 필요"

        # ── 지붕 진단 텍스트 ──
        roof_type = building.get("roofCdNm", "정보 없음")
        vulnerable_roofs = ["슬레이트", "판넬", "기와", "목재", "아스팔트싱글", "샌드위치판넬"]
        is_vulnerable_roof = any(vr in roof_type for vr in vulnerable_roofs)
        
        if roof_type == "정보 없음":
            roof_diag = "지붕구조 정보가 없어 복사열 취약 여부를 판단할 수 없습니다."
        elif is_vulnerable_roof:
            roof_diag = f"지붕구조 '{roof_type}'는 폭염 시 복사열 흡수가 높아 실내 온도 상승의 주요 원인입니다. 쿨루프(Cool Roof) 시공을 강력 권장합니다."
        else:
            roof_diag = f"지붕구조 '{roof_type}'는 열 차단 성능이 비교적 양호합니다."

        # ── 폭염 진단 텍스트 ──
        max_temp_val = climate.get("max_temp", 35.0)
        hw_days = climate.get("heatwave_days", 10)
        tn_days = climate.get("tropical_nights", 10)
        
        if max_temp_val >= 38:
            temp_diag = f"여름 최고기온 {max_temp_val}℃, 폭염일수 {hw_days}일로 극심한 폭염 지역입니다. 열대야 {tn_days}일은 야간 냉방 부담을 가중시킵니다."
        elif max_temp_val >= 35:
            temp_diag = f"여름 최고기온 {max_temp_val}℃, 폭염일수 {hw_days}일로 폭염 주의 지역입니다. 냉방 사각지대 해소가 시급합니다."
        else:
            temp_diag = f"여름 최고기온 {max_temp_val}℃, 폭염일수 {hw_days}일로 비교적 온화한 기후입니다."

        # ── 고령자 진단 텍스트 ──
        elderly_r = population.get("elderly_ratio", 18.0)
        solo_r = population.get("solo_elderly_ratio", 5.0)
        
        if elderly_r >= 30:
            pop_diag = f"고령화율 {elderly_r}%로 초고령사회에 해당합니다. 독거노인 비율 {solo_r}%는 폭염 시 고독사 위험을 크게 높입니다. 긴급 안부 확인 및 방문 간호 체계가 반드시 필요합니다."
        elif elderly_r >= 20:
            pop_diag = f"고령화율 {elderly_r}%로 고령사회에 해당합니다. 독거노인 비율 {solo_r}%에 대한 돌봄 서비스 확대가 권장됩니다."
        elif elderly_r >= 14:
            pop_diag = f"고령화율 {elderly_r}%로 고령화사회에 해당합니다. 취약계층 대상 폭염 대비 예방적 관리가 필요합니다."
        else:
            pop_diag = f"고령화율 {elderly_r}%로 상대적으로 젊은 인구 구조입니다."

        # ── 썸네일 이미지 ──
        report_thumbnail = f"{BACKEND_URL}/api/thumbnail?lat={lat}&lng={lng}"

        # ── 데이터 신뢰도 산출 ──
        conf_bldg = 1.0 if building.get("source") != "no_data" else 0.2
        conf_climate = 1.0 if climate.get("source") == "kma_api" else 0.6
        conf_pop = 1.0 if population.get("source") == "kosis_api" else 0.6
        
        confidence_pct = round((conf_bldg * 0.4 + conf_climate * 0.3 + conf_pop * 0.3) * 100)
        if confidence_pct >= 80:
            confidence_label = "정밀 분석"
        elif confidence_pct >= 55:
            confidence_label = "추정 데이터 포함"
        else:
            confidence_label = "현장 확인 권장"

        log.info(f"[/heatwave-analyze] 완료 | 위험도={risk['riskIndex']} ({risk['riskLevel']}) 신뢰도={confidence_pct}%")

        return jsonify({
            "status":           "Heatwave Risk Engine v1.0 Active",
            "region":           region_name,
            "thumbnail":        report_thumbnail,
            "confidenceScore":  confidence_pct,
            "confidenceLabel":  confidence_label,
            
            # 핵심: 폭염 위험도 지수
            "riskIndex":    risk["riskIndex"],
            "riskLevel":    risk["riskLevel"],
            "riskColor":    risk["riskColor"],
            "riskEmoji":    risk["riskEmoji"],
            
            # 세부 점수
            "riskBreakdown": {
                "aging":       risk["ageRisk"],
                "elderly":     risk["elderlyRisk"],
                "temperature": risk["tempRisk"],
            },
            "weights":   risk["weights"],
            "radar":     risk["radar"],
            
            # 건축물 정보
            "building": {
                "buildAge":    building.get("buildAge"),
                "buildYear":   building.get("buildYear"),
                "useAprvDe":   building.get("useAprvDe"),
                "roofType":    building.get("roofCdNm"),
                "structure":   building.get("strctCdNm"),
                "purpose":     building.get("mainPurpsCdNm"),
                "floorInfo":   f"지상 {building.get('grndFlrCnt', '?')}층 / 지하 {building.get('ugrndFlrCnt', '?')}층",
                "hhldCnt":     building.get("hhldCnt"),
                "totArea":     building.get("totArea"),
                "energyGrade": building.get("engrEfcRtNm"),
                "isVulnerableRoof": is_vulnerable_roof,
                "source":      building.get("source"),
            },
            
            # 기후 정보
            "climate": {
                "maxTemp":        climate.get("max_temp"),
                "heatwaveDays":   climate.get("heatwave_days"),
                "avgSummerTemp":  climate.get("avg_summer_temp"),
                "tropicalNights": climate.get("tropical_nights"),
                "stationId":     climate.get("station_id"),
                "source":        climate.get("source"),
            },
            
            # 인구 정보
            "population": {
                "elderlyRatio":     population.get("elderly_ratio"),
                "soloElderlyRatio": population.get("solo_elderly_ratio"),
                "totalPopulation":  population.get("total_population"),
                "elderlyPopulation": population.get("elderly_population"),
                "source":           population.get("source"),
            },
            
            # 진단 텍스트
            "diagnosis": {
                "age":         age_diag,
                "roof":        roof_diag,
                "temperature": temp_diag,
                "population":  pop_diag,
                "overall":     f"{risk['riskEmoji']} {region_name} 폭염 주거 위험도 {risk['riskIndex']}점 ({risk['riskLevel']}) — 종합 신뢰도 {confidence_pct}%",
            },
        })

    except Exception as e:
        log.error(f"[/heatwave-analyze] 예외: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# 엔드포인트: 쓰레기 배출 정보 (기존 보존)
# ─────────────────────────────────────────────────────────────
@app.route('/api/waste', methods=['GET'])
def get_waste_info():
    try:
        region = request.args.get('region', '').strip()
        if not region:
            return jsonify({"error": "region 파라미터가 필요합니다."}), 400

        if WASTE_DF is None:
            return jsonify({"error": "CSV 데이터 로드 실패"}), 500

        parts = region.split()
        gu_kw   = parts[0] if parts else region
        dong_kw = parts[1] if len(parts) > 1 else ""

        mask = WASTE_DF['시군구명'].str.contains(gu_kw, na=False)
        if dong_kw:
            mask2 = WASTE_DF['관리구역대상지역명'].str.contains(dong_kw, na=False)
            combined = WASTE_DF[mask & mask2]
            if combined.empty:
                combined = WASTE_DF[mask]
        else:
            combined = WASTE_DF[mask]

        if combined.empty and dong_kw:
            combined = WASTE_DF[WASTE_DF['관리구역대상지역명'].str.contains(dong_kw, na=False)]
            if combined.empty:
                combined = WASTE_DF[WASTE_DF['시군구명'].str.contains(gu_kw, na=False)]

        if combined.empty:
            return jsonify({"found": False, "message": "해당 지역의 배출 정보를 찾을 수 없습니다."})

        row = combined.iloc[0]
        def sg(col):
            v = row.get(col, '')
            return '' if pd.isna(v) else str(v)

        return jsonify({
            "found": True,
            "sigungu":     sg('시군구명'),
            "region":      sg('관리구역대상지역명'),
            "placeType":   sg('배출장소유형'),
            "place":       sg('배출장소'),
            "wasteMethod": sg('생활쓰레기배출방법'),
            "foodMethod":  sg('음식물쓰레기배출방법'),
            "recycleMethod": sg('재활용품배출방법'),
            "wasteDay":    sg('생활쓰레기배출요일'),
            "foodDay":     sg('음식물쓰레기배출요일'),
            "recycleDay":  sg('재활용품배출요일'),
            "wasteStart":  sg('생활쓰레기배출시작시각'),
            "wasteEnd":    sg('생활쓰레기배출종료시각'),
            "foodStart":   sg('음식물쓰레기배출시작시각'),
            "foodEnd":     sg('음식물쓰레기배출종료시각'),
            "recycleStart": sg('재활용품배출시작시각'),
            "recycleEnd":  sg('재활용품배출종료시각'),
            "noCollectDay": sg('미수거일'),
            "deptName":    sg('관리부서명'),
            "deptPhone":   sg('관리부서전화번호'),
        })
    except Exception as e:
        log.error(f"[/api/waste] {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# 엔드포인트: 지역 목록 반환 (전국 읍면동 동적 검색용)
# ─────────────────────────────────────────────────────────────
@app.route('/api/regions', methods=['GET'])
def get_regions():
    try:
        if POP_ELDERLY_DF is None:
            return jsonify({"error": "CSV 데이터 로드 실패"}), 500
        # 행정구역 목록 반환 (예: "서울특별시 종로구 청운효자동(1111051500)")
        regions = POP_ELDERLY_DF['행정구역'].dropna().astype(str).str.strip().tolist()
        return jsonify({"regions": regions})
    except Exception as e:
        log.error(f"[/api/regions] {e}")
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────────────────────
# 서버 실행
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    load_geo_cache()
    log.info("=" * 60)
    log.info("  🌡️  기후 재난(폭염) 주거 안전 진단 시스템 시작")
    log.info("  Endpoints:")
    log.info("    POST /api/heatwave-analyze  — 폭염 주거 위험도 분석")
    log.info("    POST /api/ai-report         — AI 복지 정책 리포트")
    log.info("    GET  /api/waste             — 쓰레기 배출 정보")
    log.info("    GET  /api/thumbnail         — 지도 썸네일 프록시")
    log.info("    GET  /api/roadview          — 로드뷰 이미지 프록시")
    log.info("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
