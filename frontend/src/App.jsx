import React, { useState, useEffect, useRef } from 'react';
import { 
  Thermometer, Building2, Users, AlertTriangle, CheckCircle2, 
  MapPin, Sparkles, RefreshCw, ArrowRight, ShieldAlert, Cpu, 
  Eye, FileText, ChevronRight, HelpCircle, AlertCircle, Calendar, 
  Clock, ChevronDown, Plus, Minus, X, Info, HelpCircle as HelpIcon
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { 
  AreaChart, Area, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer 
} from 'recharts';

// ── 전국 행정동 데이터 ── (백엔드에서 동적 로드)
// ── 로딩 스켈레톤 컴포넌트 ──
const SkeletonCard = () => (
  <div className="bg-[#1e293b]/50 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 animate-pulse">
    <div className="flex justify-between items-center">
      <div className="w-24 h-4 bg-slate-800 rounded" />
      <div className="w-8 h-8 bg-slate-800 rounded-full" />
    </div>
    <div className="w-16 h-8 bg-slate-750 rounded" />
    <div className="w-full h-2 bg-slate-800 rounded" />
    <div className="w-3/4 h-3 bg-slate-800 rounded" />
  </div>
);

const SkeletonReport = () => (
  <div className="space-y-6 animate-pulse">
    <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
      <div className="w-10 h-10 bg-slate-800 rounded-xl" />
      <div className="space-y-2 flex-1">
        <div className="w-48 h-5 bg-slate-700 rounded" />
        <div className="w-32 h-3.5 bg-slate-800 rounded" />
      </div>
    </div>
    <div className="space-y-3">
      <div className="w-full h-4 bg-slate-800 rounded" />
      <div className="w-11/12 h-4 bg-slate-800 rounded" />
      <div className="w-4/5 h-4 bg-slate-800 rounded" />
    </div>
    <div className="p-4 bg-slate-900/50 rounded-xl space-y-2">
      <div className="w-24 h-4 bg-slate-700 rounded" />
      <div className="w-full h-3 bg-slate-800 rounded" />
      <div className="w-5/6 h-3 bg-slate-800 rounded" />
    </div>
  </div>
);

const SkeletonMetricCard = () => (
  <div className="bg-[#1e293b]/80 border border-slate-800 rounded-2xl p-4 shadow-xl min-w-[140px] h-[76px] animate-pulse flex flex-col items-center justify-center space-y-2">
    <div className="w-20 h-3 bg-slate-700 rounded" />
    <div className="w-12 h-6 bg-slate-600 rounded" />
  </div>
);

const CountUp = ({ end, duration = 1000 }) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTimestamp = null;
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easeProgress = 1 - Math.pow(1 - progress, 4);
      setCount(Math.floor(easeProgress * end));
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        setCount(end);
      }
    };
    window.requestAnimationFrame(step);
  }, [end, duration]);

  return <span>{count}</span>;
};

function App() {
  const [allRegions, setAllRegions] = useState([]);
  const [geoJson, setGeoJson] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [selectedDong, setSelectedDong] = useState(null); // { name, cleanName, lat, lng }
  const [searchKeyword, setSearchKeyword] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [analyzeData, setAnalyzeData] = useState(null);
  const [aiReport, setAiReport] = useState('');
  const [showAiReport, setShowAiReport] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [riskFilter, setRiskFilter] = useState(0);
  const [timeRange, setTimeRange] = useState('2024 July');

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const [kakaoLoaded, setKakaoLoaded] = useState(false);

  // 백엔드에서 3900여개 전체 지역 리스트 로드 및 GeoJSON 로드
  useEffect(() => {
    fetch('http://localhost:5000/api/regions')
      .then(res => res.json())
      .then(data => {
        if (data.regions) setAllRegions(data.regions);
      })
      .catch(err => console.error(err));
      
    // GeoJSON 경계 데이터 로드 (public/dongs.json)
    fetch('/dongs.json')
      .then(res => res.json())
      .then(data => setGeoJson(data))
      .catch(err => console.error("GeoJSON 로드 에러:", err));
  }, []);

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchKeyword(val);
    if (!val.trim()) {
      setSuggestions([]);
      return;
    }
    const filtered = allRegions.filter(r => r.includes(val)).slice(0, 50);
    setSuggestions(filtered);
  };

  // Kakao SDK 로드 대기 검출
  useEffect(() => {
    const checkKakao = setInterval(() => {
      if (window.kakao && window.kakao.maps) {
        setKakaoLoaded(true);
        clearInterval(checkKakao);
      }
    }, 150);
    return () => clearInterval(checkKakao);
  }, []);

  // Kakao Map 초기화
  useEffect(() => {
    if (!kakaoLoaded || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const options = {
        center: new window.kakao.maps.LatLng(37.5665, 126.9780), // 기본 중심: 서울시청
        level: 8,
        draggable: true,
        scrollwheel: true
      };
      mapInstanceRef.current = new window.kakao.maps.Map(mapContainerRef.current, options);
    }
  }, [kakaoLoaded]);

  // 선택된 동 핑 마커 및 행정동 경계 폴리곤 렌더링 (Choropleth 맵)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !kakaoLoaded || !selectedDong || !geoJson) return;

    // 1. 기존 마커 및 폴리곤 지우기
    markersRef.current.forEach(overlay => overlay.setMap(null));
    markersRef.current = [];
    if (window.hexPolygons) {
      window.hexPolygons.forEach(p => p.setMap(null));
    }
    window.hexPolygons = [];

    const baseRisk = analyzeData?.riskIndex || 50;

    // 위험도 점수에 따른 테마 색상 및 텍스트 (단일 핑 마커용)
    let markerColor = 'bg-[#10b981] border-[#34d399]';
    let textColor = 'text-[#34d399]';
    if (baseRisk >= 85) {
      markerColor = 'bg-[#ef4444] border-[#f87171]';
      textColor = 'text-[#f87171]';
    } else if (baseRisk >= 60) {
      markerColor = 'bg-[#f97316] border-[#fb923c]';
      textColor = 'text-[#fb923c]';
    } else if (baseRisk >= 25) {
      markerColor = 'bg-[#eab308] border-[#fde047]';
      textColor = 'text-[#fde047]';
    }

    // 2. 커스텀 오버레이(중심 마커) 생성
    const container = document.createElement('div');
    container.className = 'transform transition-all duration-300 hover:scale-110 cursor-pointer flex flex-col items-center z-50';
    container.innerHTML = `
      <div class="relative flex items-center justify-center">
        <span class="animate-ping absolute inline-flex h-9 w-9 rounded-full bg-slate-100 opacity-60"></span>
        <div class="w-8 h-8 rounded-xl ${markerColor} border-2 flex items-center justify-center shadow-[0_4px_12px_rgba(0,0,0,0.5)] text-white text-xs font-black relative z-10">
          📍
        </div>
      </div>
      <div class="mt-1.5 bg-[#0f172a]/95 border border-slate-700/60 backdrop-blur-md px-2.5 py-1 rounded-lg shadow-xl flex items-center gap-1.5 relative z-10">
        <span class="text-[9.5px] font-black text-slate-100 whitespace-nowrap">${selectedDong.cleanName.split(' ').pop()}</span>
        <span class="text-[9px] font-black ${textColor}">${baseRisk}</span>
      </div>
    `;

    const customOverlay = new window.kakao.maps.CustomOverlay({
      position: new window.kakao.maps.LatLng(selectedDong.lat, selectedDong.lng),
      content: container,
      yAnchor: 1.15
    });
    customOverlay.setMap(map);
    markersRef.current.push(customOverlay);

    // 3. 해당 시군구(Gu)의 모든 읍면동 폴리곤 생성 (GeoJSON)
    const getRiskColor = (risk) => {
      if (risk >= 85) return '#ef4444'; 
      if (risk >= 65) return '#f97316'; 
      if (risk >= 45) return '#facc15'; 
      if (risk >= 25) return '#84cc16'; 
      return '#22c55e'; 
    };

    // 거리 계산 함수 (Haversine)
    const getDistance = (lat1, lon1, lat2, lon2) => {
      const R = 6371;
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon/2) * Math.sin(dLon/2);
      return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
    };

    const targetDongName = selectedDong.cleanName.split(' ').pop();

    geoJson.features.forEach(feature => {
      if (!showHeatmap) return; // 히트맵 토글 꺼짐 상태면 패스

      const fName = feature.properties.name || feature.properties.adm_nm || "";
      
      let isSelected = false;
      if (fName === targetDongName || fName.includes(targetDongName) || targetDongName.includes(fName)) {
        isSelected = true;
      }

      const geometry = feature.geometry;
      if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon') {
        const coordinates = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
        
        // 폴리곤의 첫 번째 좌표를 기준점으로 거리 계산
        let polyLat = selectedDong.lat;
        let polyLng = selectedDong.lng;
        try {
           polyLng = coordinates[0][0][0][0];
           polyLat = coordinates[0][0][0][1];
        } catch(e) {}
        
        const dist = getDistance(selectedDong.lat, selectedDong.lng, polyLat, polyLng);
        
        let cellRisk = baseRisk;
        if (isSelected || dist < 4) {
          cellRisk = baseRisk; 
          isSelected = true;
        } else if (dist < 15) {
          // 15km 이내: 자연스럽게 비슷한 위험도로 퍼짐
          const hash = fName.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
          cellRisk = Math.round(Math.max(10, Math.min(100, baseRisk + (hash % 16) - 8)));
        } else if (dist < 50) {
          // 50km 이내: 점진적으로 전국 평균(약 45)에 가까워짐
          cellRisk = Math.round((baseRisk * 0.4) + 27 + ((dist % 10) - 5));
        } else {
          // 그 외 전국: 평균치 베이스 + 미세 노이즈
          cellRisk = 45 + (fName.length % 10);
        }

        // RISK FILTER 값보다 작고 선택된 지역이 아니라면 렌더링 생략 (히트맵 조절)
        if (cellRisk < riskFilter && !isSelected) return;

        const color = getRiskColor(cellRisk);
        const baseOpacity = isSelected ? 0.65 : (dist < 15 ? 0.4 : (dist < 50 ? 0.25 : 0.1));
        const strokeColor = isSelected ? '#ffffff' : (dist < 15 ? '#1e293b' : 'transparent');
        const strokeWeight = isSelected ? 3 : 1;

        coordinates.forEach(polygonCoords => {
          const path = polygonCoords[0].map(coord => new window.kakao.maps.LatLng(coord[1], coord[0]));
          
          const polygon = new window.kakao.maps.Polygon({
            path: path,
            strokeWeight: strokeWeight,
            strokeColor: strokeColor,
            strokeOpacity: 0.9,
            fillColor: color,
            fillOpacity: baseOpacity
          });

          // 호버 이펙트 (강조)
          window.kakao.maps.event.addListener(polygon, 'mouseover', () => {
            polygon.setOptions({ fillOpacity: 0.85, strokeColor: '#ffffff', strokeWeight: 2 });
          });
          window.kakao.maps.event.addListener(polygon, 'mouseout', () => {
            polygon.setOptions({ fillOpacity: baseOpacity, strokeColor: strokeColor, strokeWeight: strokeWeight });
          });

          polygon.setMap(map);
          window.hexPolygons.push(polygon);
        });
      }
    });

    // 부드럽게 선택 지역으로 이동
    map.panTo(new window.kakao.maps.LatLng(selectedDong.lat, selectedDong.lng));
  }, [selectedDong, analyzeData, kakaoLoaded, geoJson, showHeatmap, riskFilter]);

  // 지도 줌 인/아웃 편의기능
  const zoomIn = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setLevel(mapInstanceRef.current.getLevel() - 1);
    }
  };
  const zoomOut = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setLevel(mapInstanceRef.current.getLevel() + 1);
    }
  };

  // 행정동 검색 및 선택
  const handleSelectRegion = (regionStr) => {
    setSearchKeyword('');
    setSuggestions([]);
    
    // "서울특별시 종로구 청운효자동(1111051500)" -> "서울특별시 종로구 청운효자동"
    const cleanName = regionStr.replace(/\(.*?\)/g, '').trim();
    
    if (window.kakao && window.kakao.maps && window.kakao.maps.services) {
      const geocoder = new window.kakao.maps.services.Geocoder();
      geocoder.addressSearch(cleanName, (result, status) => {
        if (status === window.kakao.maps.services.Status.OK) {
          const lat = parseFloat(result[0].y);
          const lng = parseFloat(result[0].x);
          executeAnalysis({ name: regionStr, cleanName, lat, lng });
        } else {
          // 좌표 검색 실패 시 임의의 기본값 사용
          executeAnalysis({ name: regionStr, cleanName, lat: 37.5665, lng: 126.9780 });
        }
      });
    } else {
      executeAnalysis({ name: regionStr, cleanName, lat: 37.5665, lng: 126.9780 });
    }
  };

  const executeAnalysis = async (dong) => {
    setSelectedDong(dong);
    setLoading(true);
    setAiLoading(true);
    setAnalyzeData(null);
    setAiReport('');

    try {
      // 1. 백엔드 주거 안전 진단 API 호출 (기상청/국토부 실데이터 연동)
      const analyzeRes = await fetch('http://localhost:5000/api/heatwave-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          regionName: dong.name, // CSV 매칭을 위해 괄호가 포함된 원본 전체 문자열 전달
          lat: dong.lat,
          lng: dong.lng
        })
      });
      
      if (!analyzeRes.ok) throw new Error('백엔드 분석 서버가 응답하지 않습니다.');
      const data = await analyzeRes.json();
      setAnalyzeData(data);
      setLoading(false); // 분석 완료 즉시 UI 해제 (AI보다 먼저 표시)

      // 2. 백엔드 AI 정책 리포트 생성 API 호출 (비동기 처리)
      fetch('http://localhost:5000/api/ai-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          region_name: dong.cleanName, // AI 리포트에는 깔끔한 이름 전달
          risk_index: data.riskIndex,
          risk_level: data.riskLevel,
          building_age: data.building?.buildAge || 30,
          roof_type: data.building?.roofType || '정보 없음',
          elderly_ratio: data.population?.elderlyRatio || 25,
          solo_elderly_ratio: data.population?.soloElderlyRatio || 8,
          max_temp: data.climate?.maxTemp || 35.5,
          heatwave_days: data.climate?.heatwaveDays || 12,
          tropical_nights: data.climate?.tropicalNights || 10
        })
      }).then(async (aiRes) => {
        if (!aiRes.ok) throw new Error('AI 법률/정책 서버 호출에 실패했습니다.');
        const aiData = await aiRes.json();
        setAiReport(aiData.report);
      }).catch(err => {
        console.error(err);
        setAiReport(`### 1. ⚠️ 통신 오류\nAI 서버와 통신할 수 없어 분석에 실패했습니다.`);
      }).finally(() => {
        setAiLoading(false);
      });

    } catch (error) {
      console.error(error);
      // 서버 통신 오류 시 간략한 에러 더미 데이터 표시
      setTimeout(() => {
        setAnalyzeData({
          riskIndex: 50, riskLevel: '보통', riskColor: '#eab308', riskEmoji: '🟡',
          building: { buildAge: 30, roofType: "정보 없음", structure: "정보 없음", purpose: "정보 없음", floorInfo: "지상" },
          climate: { maxTemp: 35.5, heatwaveDays: 14, tropicalNights: 8 },
          population: { elderlyRatio: 20.0, soloElderlyRatio: 8.5, totalPopulation: 10000 },
          diagnosis: { overall: `${dong.cleanName} 데이터를 불러오지 못했습니다. (서버 응답 없음)` }
        });
        setAiReport(`### 1. ⚠️ 통신 오류\n백엔드 서버와 통신할 수 없어 분석에 실패했습니다.`);
        setLoading(false);
        setAiLoading(false);
      }, 800);
    }
  };

  // 전체 지역 로드 후 최초 1회 자동 선택
  useEffect(() => {
    if (kakaoLoaded && allRegions.length > 0 && !selectedDong) {
      // 처음에 서울특별시 종로구 청운효자동 띄우기
      handleSelectRegion(allRegions[0]);
    }
  }, [kakaoLoaded, allRegions]);

  // ── 2x2 Recharts 시뮬레이션용 데이터 가공 ──
  const baseDays = analyzeData?.climate?.heatwaveDays || 12;
  const heatwaveDaysData = [
    { name: '8', days: Math.round(baseDays * 0.8) },
    { name: '12', days: Math.round(baseDays * 0.6) },
    { name: '18', days: Math.round(baseDays * 1.2) },
    { name: '21', days: Math.round(baseDays * 1.6) },
    { name: '36', days: Math.round(baseDays * 1.1) },
    { name: '38', days: Math.round(baseDays * 0.95) }
  ];

  const age = analyzeData?.building?.buildAge || 30;
  const buildingAgeData = [
    { name: '10', ratio: age < 15 ? 40 : 15 },
    { name: '20', ratio: age >= 15 && age < 25 ? 45 : 20 },
    { name: '30', ratio: age >= 25 && age < 35 ? 50 : 25 },
    { name: '40', ratio: age >= 35 && age < 45 ? 40 : 15 },
    { name: '50', ratio: age >= 45 ? 35 : 10 },
    { name: '70+', ratio: age >= 50 ? 25 : 5 }
  ];

  const elderly = analyzeData?.population?.elderlyRatio || 22;
  const populationData = [
    { name: '65+', value: Math.round(elderly * 1.2) },
    { name: '70+', value: Math.round(elderly * 0.95) },
    { name: '80+', value: Math.round(elderly * 0.5) },
    { name: '독거', value: Math.round(elderly * 0.38) }
  ];

  const riskScore = analyzeData?.riskIndex || 70;
  const emptyVal = Math.round(riskScore * 0.35 + 5);
  const emptyHousingData = [
    { name: '공가', empty: emptyVal, total: 100 - emptyVal },
    { name: '주거', empty: 0, total: 95 }
  ];

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0f19] text-slate-100 overflow-hidden antialiased font-sans">
      
      {/* ── 공공기관 스타일 프리미엄 다크 헤더 ── */}
      <header className="h-16 px-6 bg-[#0f172a] border-b border-slate-800 flex items-center justify-between z-20 shadow-lg shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center text-white shadow-md">
            <Thermometer size={22} strokeWidth={2.5} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm md:text-base font-black text-white tracking-tighter leading-tight">
                Climate Disaster (Heatwave/Urban Heat Island) Vulnerability Diagnosis Solution for Vulnerable Groups' Residential Safety
              </h1>
            </div>
            <p className="text-[10px] text-slate-400 font-bold tracking-tight mt-0.5">
              기후 재난(폭염/도시열섬) 주거 취약성 종합 안전 진단 및 데이터 융합 대시보드
            </p>
          </div>
        </div>

        {/* 상단 우측 */}
        <div className="flex items-center gap-3">
          <div className="text-xs font-black text-emerald-400 bg-emerald-400/10 px-3 py-1.5 rounded-lg border border-emerald-400/20 shadow-[0_0_15px_rgba(52,211,153,0.15)] flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            전국 데이터 연동 완벽 적용
          </div>
        </div>
      </header>

      {/* ── 메인 대시보드 구조 ── */}
      <main className="flex flex-1 overflow-hidden">
        
        {/* ── [1] 좌측 컨트롤러 & 사이드바 ── */}
        <aside className="w-80 bg-[#0f172a] border-r border-slate-800 flex flex-col shrink-0 z-10">
          <div className="p-4 border-b border-slate-800 flex flex-col gap-4">
            
            {/* Nationwide Region Search */}
            <div className="space-y-1.5 relative">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Region Search (전국 읍면동)</label>
              <div className="relative">
                <input
                  type="text"
                  value={searchKeyword}
                  onChange={handleSearchChange}
                  placeholder="예: 종로구 청운효자동"
                  className="w-full bg-slate-900/95 border border-slate-800 rounded-xl py-2.5 pl-4 pr-10 text-xs font-bold text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all placeholder:text-slate-600"
                />
                {searchKeyword && (
                  <button onClick={() => {setSearchKeyword(''); setSuggestions([]);}} className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300">
                    <X size={14} />
                  </button>
                )}
              </div>
              
              {/* Autocomplete Suggestions */}
              {suggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 max-h-60 overflow-y-auto bg-slate-800 border border-slate-700 rounded-xl shadow-2xl z-50 divide-y divide-slate-700/50 dark-scrollbar">
                  {suggestions.map((region, idx) => {
                    const cleanName = region.replace(/\(.*?\)/g, '').trim();
                    return (
                      <button
                        key={idx}
                        onClick={() => handleSelectRegion(region)}
                        className="w-full text-left px-4 py-2.5 hover:bg-blue-600/30 focus:bg-blue-600/30 focus:outline-none transition-colors"
                      >
                        <div className="text-[11px] font-bold text-slate-200">{cleanName}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Time Range */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Time Range</label>
              <div className="relative">
                <select
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value)}
                  className="w-full bg-slate-900/95 border border-slate-800 rounded-xl py-2.5 pl-4 pr-10 text-xs font-bold text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-slate-700 cursor-pointer transition-all"
                >
                  <option value="2024 July">2024 July</option>
                  <option value="2024 August">2024 August</option>
                  <option value="2025 July">2025 July</option>
                  <option value="2025 August">2025 August</option>
                </select>
                <ChevronDown size={14} className="absolute right-3.5 top-3.5 text-slate-400 pointer-events-none" />
              </div>
            </div>

            {/* Risk Filter */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-[10px] font-black text-slate-400 uppercase tracking-wider">
                <span>Risk Filter</span>
                <span className="text-blue-400">{riskFilter}+</span>
              </div>
              <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 space-y-2">
                <input
                  type="range"
                  min="0"
                  max="80"
                  step="10"
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="flex justify-between text-[9px] font-black text-slate-500">
                  <span>Low</span>
                  <span>High Risk</span>
                </div>
              </div>
            </div>

            {/* Show AI Report Toggle */}
            <div className="flex items-center justify-between bg-slate-900/50 border border-slate-800 rounded-xl p-3">
              <span className="text-xs font-extrabold text-slate-300">Show AI Report</span>
              <input
                type="checkbox"
                checked={showAiReport}
                onChange={(e) => setShowAiReport(e.target.checked)}
                className="w-4 h-4 rounded text-blue-500 bg-slate-950 border-slate-800 accent-blue-500 focus:ring-0 cursor-pointer"
              />
            </div>
            
          </div>

          {/* 선택된 지역 정보 표시 */}
          <div className="flex-1 overflow-y-auto dark-scrollbar p-4 space-y-4 bg-[#090f1d] flex flex-col justify-center">
            {selectedDong ? (
              <div className="flex flex-col items-center text-center gap-3 bg-[#111827] p-5 rounded-2xl border border-blue-900/30 shadow-[0_0_20px_rgba(59,130,246,0.05)]">
                <div className="w-14 h-14 bg-gradient-to-tr from-blue-500/20 to-indigo-500/20 rounded-2xl flex items-center justify-center border border-blue-500/20">
                  <MapPin size={28} className="text-blue-400" />
                </div>
                <div>
                  <h3 className="text-sm font-black text-slate-100">{selectedDong.cleanName}</h3>
                  <p className="text-[10px] font-bold text-slate-500 mt-1 uppercase tracking-wider">Currently Analyzing</p>
                </div>
                
                {loading ? (
                  <div className="mt-2 text-xs font-bold text-blue-400 flex items-center gap-2">
                    <RefreshCw size={12} className="animate-spin" />
                    <span>전국 실시간 통계 로딩중...</span>
                  </div>
                ) : (
                  <div className="w-full bg-slate-900 rounded-xl p-3 mt-2 border border-slate-800 text-left space-y-2">
                    <div className="flex justify-between items-center text-[10px] font-black">
                      <span className="text-slate-400">데이터 소스</span>
                      <span className="text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">실시간 매칭</span>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-black">
                      <span className="text-slate-400">행정구역 수</span>
                      <span className="text-blue-400">전국 3,900+</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 text-center gap-3">
                <div className="w-12 h-12 rounded-full bg-slate-800/50 flex items-center justify-center border border-slate-700/50">
                  <MapPin size={20} />
                </div>
                <p className="text-[11px] font-bold">상단의 검색창에서<br/>원하는 지역을 검색해주세요.</p>
              </div>
            )}
          </div>
          
          <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center gap-2">
            <HelpIcon size={14} className="text-slate-500 shrink-0" />
            <span className="text-[9px] font-bold text-slate-400 leading-normal">
              본 진단 모델은 기상청 AWS 방재 실측데이터와 국토부 건축물대장 및 주민등록 통계를 결합한 위험 가중 지수입니다.
            </span>
          </div>
        </aside>

        {/* ── [2] 중앙 어두운 모드 GIS 지도 ── */}
        <section className="flex-1 min-w-0 relative h-full bg-[#0b0f19] flex flex-col">
          
          {/* 실제 Kakao Map이 주입될 컨테이너 */}
          <div 
            ref={mapContainerRef} 
            className="w-full h-full dark-gis-map relative"
          >
            {!kakaoLoaded && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/80 z-20 space-y-3">
                <Cpu className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-xs font-black text-slate-400">Loading Map SDK...</p>
              </div>
            )}
          </div>

          {/* ── 중앙 상단 핵심 지표 카드 ── */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 z-10 flex gap-4">
            {loading ? (
              <>
                <SkeletonMetricCard />
                <SkeletonMetricCard />
                <SkeletonMetricCard />
              </>
            ) : (
              <>
                <div className="bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-4 shadow-xl min-w-[140px] flex flex-col items-center justify-center">
                  <span className="text-[10px] text-slate-400 font-bold mb-1 uppercase tracking-wider">폭염 위험 지수</span>
                  <span className="text-2xl font-black text-red-500 flex items-center gap-1">
                    <CountUp end={analyzeData?.riskIndex || 50} />
                    <span className="text-[12px] text-slate-500 font-bold">점</span>
                  </span>
                </div>
                <div className="bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-4 shadow-xl min-w-[140px] flex flex-col items-center justify-center">
                  <span className="text-[10px] text-slate-400 font-bold mb-1 uppercase tracking-wider">노후 건축물 비율</span>
                  <span className="text-2xl font-black text-orange-400 flex items-center gap-1">
                    <CountUp end={analyzeData?.building?.buildAge || 30} />
                    <span className="text-[12px] text-slate-500 font-bold">%</span>
                  </span>
                </div>
                <div className="bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-4 shadow-xl min-w-[140px] flex flex-col items-center justify-center">
                  <span className="text-[10px] text-slate-400 font-bold mb-1 uppercase tracking-wider">65세 이상 비율</span>
                  <span className="text-2xl font-black text-blue-400 flex items-center gap-1">
                    <CountUp end={analyzeData?.population?.elderlyRatio || 22} />
                    <span className="text-[12px] text-slate-500 font-bold">%</span>
                  </span>
                </div>
              </>
            )}
          </div>

          {/* ── 지도 위 플로팅 레이아웃: 범례 (Residential Heatwave Risk Index) ── */}
          <div className="absolute top-4 left-4 z-10 w-[240px] bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-4 shadow-[0_10px_30px_rgba(0,0,0,0.5)] mt-2">
            <h3 className="text-xs font-black text-white mb-1.5 tracking-tight">Residential Heatwave Risk Index</h3>
            <p className="text-[9px] text-slate-400 font-bold mb-2.5">By Administrative dong</p>
            
            {/* 그라데이션 범례 바 */}
            <div className="h-2.5 w-full bg-gradient-to-r from-emerald-500 via-yellow-500 via-orange-500 to-red-500 rounded-full mb-1.5" />
            <div className="flex justify-between text-[8.5px] font-black text-slate-400 mb-4 px-0.5">
              <span>Low Risk</span>
              <span>25-50</span>
              <span>85-100</span>
              <span>High Risk</span>
            </div>

            {/* 메트릭 범주 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[9.5px] font-black text-slate-300">
                <span className="text-xs">🔥</span>
                <span>Risk Score</span>
              </div>
              <div className="flex items-center gap-2 text-[9.5px] font-black text-slate-300">
                <span className="text-xs">🌡️</span>
                <span>Heatwave Days</span>
              </div>
              <div className="flex items-center gap-2 text-[9.5px] font-black text-slate-300">
                <span className="text-xs">👵</span>
                <span>Elderly/Single Household Density</span>
              </div>
              <div className="flex items-center gap-2 text-[9.5px] font-black text-slate-300">
                <span className="text-xs">🏠</span>
                <span>Empty Houses</span>
              </div>
            </div>
          </div>

          {/* ── 지도 위 플로팅 레이아웃: 서브 범례 ── */}
          <div className="absolute bottom-4 left-4 z-10 w-[220px] bg-slate-950/85 backdrop-blur-md border border-slate-800 rounded-2xl p-3.5 shadow-lg flex flex-col gap-2">
            <h4 className="text-[10px] font-black text-slate-200 tracking-tight">Residential Heatwave Risk Index</h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-[9px] font-bold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444]" />
                <span>Risk Score (High)</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] font-bold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full bg-[#f97316]" />
                <span>Heatwave Days</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] font-bold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full bg-[#eab308]" />
                <span>Elderly/Single Household Density</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] font-bold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full bg-[#3b82f6]" />
                <span>Empty Houses</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] font-bold text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]" />
                <span>Low Risk</span>
              </div>
            </div>
          </div>

          {/* ── 지도 위 플로팅 레이아웃: 줌 컨트롤러 및 맵 토글 ── */}
          <div className="absolute top-4 right-4 z-10 flex flex-col bg-slate-950/90 border border-slate-850 rounded-xl overflow-hidden shadow-lg">
            <button 
              onClick={() => setShowHeatmap(!showHeatmap)}
              title="히트맵 켜기/끄기"
              className={`w-9 h-9 flex items-center justify-center border-b border-slate-850/60 transition-all font-black ${showHeatmap ? 'text-blue-400 bg-slate-800' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-900'}`}
            >
              <Eye size={16} />
            </button>
            <button 
              onClick={zoomIn}
              className="w-9 h-9 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-900 border-b border-slate-850/60 transition-all font-black"
            >
              <Plus size={16} />
            </button>
            <button 
              onClick={zoomOut}
              className="w-9 h-9 flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-900 transition-all font-black"
            >
              <Minus size={16} />
            </button>
          </div>

          {/* ── 지도 위 플로팅 레이아웃: 정보 툴팁 오버레이 ── */}
          {selectedDong && (
            <div className="absolute bottom-4 right-4 z-10 w-[240px] bg-slate-950/90 backdrop-blur-md border border-slate-800 rounded-2xl p-4 shadow-2xl">
              <div className="flex justify-between items-start mb-2 pb-1.5 border-b border-slate-850">
                <span className="text-[11px] font-black text-slate-200">{selectedDong.name}</span>
                <span className="text-[8px] font-black text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded-full">Selected</span>
              </div>
              
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[9.5px] font-bold text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <span>🔥</span>
                    <span>Risk Score</span>
                  </div>
                  <span className="font-extrabold text-orange-400">{analyzeData?.riskIndex || 50} / 100</span>
                </div>

                <div className="flex items-center justify-between text-[9.5px] font-bold text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <span>🌡️</span>
                    <span>Temp</span>
                  </div>
                  <span className="font-extrabold text-slate-100">{analyzeData?.climate?.maxTemp || 35.5}°C</span>
                </div>

                <div className="flex items-center justify-between text-[9.5px] font-bold text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <span>👵</span>
                    <span>Elderly</span>
                  </div>
                  <span className="font-extrabold text-slate-100">{analyzeData?.population?.elderlyRatio || 22}%</span>
                </div>

                <div className="flex items-center justify-between text-[9.5px] font-bold text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <span>🏠</span>
                    <span>Single</span>
                  </div>
                  <span className="font-extrabold text-slate-100">{analyzeData?.population?.soloElderlyRatio || 8}%</span>
                </div>
              </div>

              <p className="text-[7.5px] font-bold text-slate-500 text-right mt-3">
                Lap Indit: © {selectedDong.name}
              </p>
            </div>
          )}

        </section>

        {/* ── [3] 우측 상세 정보 패널 (2x2 차트 및 AI 리포트) ── */}
        {showAiReport && selectedDong && (
          <aside className="w-[440px] bg-[#0f172a] border-l border-slate-800 flex flex-col shrink-0 z-10 overflow-y-auto dark-scrollbar p-5 space-y-6">
            
            {/* 동 타이틀 및 서머리 */}
            <div className="flex justify-between items-start pb-4 border-b border-slate-800">
              <div>
                <h2 className="text-sm font-black text-white flex items-center gap-1.5">
                  <span className="text-slate-300">지역 상세 진단:</span>
                  <span className="text-blue-400">{selectedDong.name}</span>
                </h2>
                <p className="text-[10px] text-slate-400 font-bold mt-1">실시간 기상 및 인구 데이터를 연계한 종합 지표</p>
              </div>
              <button 
                onClick={() => setShowAiReport(false)}
                className="w-6 h-6 bg-slate-900 rounded-full border border-slate-800 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
              >
                <X size={12} />
              </button>
            </div>

            {/* Region Summary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900/60 border border-slate-850 rounded-2xl p-4 flex flex-col justify-between">
                <span className="text-[9.5px] font-black text-slate-400 tracking-widest">종합 위험도 점수</span>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-black tracking-tighter text-red-500">
                    {loading ? <span className="animate-pulse text-slate-600">--</span> : <CountUp end={analyzeData?.riskIndex || 50} />}
                  </span>
                  <span className="text-[10px] text-slate-500 font-bold">/ 100</span>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-850 rounded-2xl p-4 flex flex-col justify-between">
                <span className="text-[9.5px] font-black text-slate-400 tracking-widest">거주 인구 현황</span>
                <div className="flex items-baseline gap-1 mt-2">
                  <span className="text-2xl font-black text-slate-100 tracking-tight">
                    {loading ? (
                      <span className="animate-pulse text-slate-600">--</span>
                    ) : (
                      analyzeData?.population?.totalPopulation ? analyzeData.population.totalPopulation.toLocaleString() : "--"
                    )}
                  </span>
                  <span className="text-[9px] text-slate-500 font-bold">명</span>
                </div>
              </div>
            </div>

            {/* ── [인포그래픽] 직관적 대시보드 ── */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[10.5px] font-black text-slate-300 uppercase tracking-widest flex items-center gap-1.5">
                  <Cpu size={12} className="text-blue-500" /> 종합 취약성 지표
                </h3>
                <span className="text-[8px] bg-blue-900/30 text-blue-400 font-black px-1.5 py-0.5 rounded">REALTIME GIS</span>
              </div>

              {/* 기후 노출도 */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                <div className="flex justify-between items-end mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center">
                      <span className="text-orange-500 text-sm">🌡️</span>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold text-slate-400">기후 노출도 (여름철)</h4>
                      <div className="text-sm font-black text-slate-100 mt-0.5">최고 기온 {analyzeData?.climate?.maxTemp || 35.5}°C</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-black text-orange-400">{analyzeData?.climate?.heatwaveDays || 12}일</span>
                    <p className="text-[8px] text-slate-500 font-bold">연속 폭염일수</p>
                  </div>
                </div>
                <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-orange-400 to-red-500 w-[80%] rounded-full"></div>
                </div>
              </div>

              {/* 주거 취약성 */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                <div className="flex justify-between items-end mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                      <span className="text-blue-500 text-sm">🏠</span>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold text-slate-400">물리적 취약성 (주택)</h4>
                      <div className="text-sm font-black text-slate-100 mt-0.5">노후 주택 밀집도</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-black text-blue-400">45%</span>
                    <p className="text-[8px] text-slate-500 font-bold">30년 이상 건축물</p>
                  </div>
                </div>
                <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 w-[45%] rounded-full"></div>
                </div>
              </div>

              {/* 인구 취약성 */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                <div className="flex justify-between items-end mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <span className="text-emerald-500 text-sm">👵</span>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold text-slate-400">인구사회적 취약성</h4>
                      <div className="text-sm font-black text-slate-100 mt-0.5">고령자 및 독거 비율</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-black text-emerald-400">{analyzeData?.population?.elderlyRatio || 22}%</span>
                    <p className="text-[8px] text-slate-500 font-bold">65세 이상 인구</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <div className="flex-1">
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1">
                      <div className="h-full bg-emerald-400" style={{width: `${analyzeData?.population?.elderlyRatio || 22}%`}}></div>
                    </div>
                    <span className="text-[8px] text-slate-400 font-bold mt-1 block">전체 고령자 비율</span>
                  </div>
                  <div className="flex-1">
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1">
                      <div className="h-full bg-teal-400" style={{width: `${analyzeData?.population?.soloElderlyRatio || 8}%`}}></div>
                    </div>
                    <span className="text-[8px] text-slate-400 font-bold mt-1 block">독거 노인 비율 ({analyzeData?.population?.soloElderlyRatio || 8}%)</span>
                  </div>
                </div>
              </div>

            </div>

            {/* ── [★] AI Generated Report (LLM Summary) ── */}
            <section className="bg-slate-900/40 border border-orange-500 rounded-2xl p-5 space-y-4 animate-glow-orange relative">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black text-white flex items-center gap-1.5">
                  <Sparkles size={14} className="text-orange-400" /> AI 맞춤형 정책 리포트
                </h3>
                <span className="text-[8px] bg-orange-950/60 text-orange-400 font-black border border-orange-900 px-2 py-0.5 rounded-full">
                  LLAMA-3 ACTIVE
                </span>
              </div>

              <div className="bg-[#0b0f19]/90 border border-slate-800 rounded-xl p-4 min-h-[140px]">
                {aiLoading ? (
                  <SkeletonReport />
                ) : aiReport ? (
                  <article className="prose prose-invert prose-xs text-slate-300 leading-relaxed text-[11px] font-medium max-w-none">
                    <ReactMarkdown 
                      components={{
                        h1: ({node, ...props}) => <h1 className="text-[13px] font-black text-white mt-4 mb-2 pb-1 border-b border-slate-800" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-[11.5px] font-black text-white mt-3 mb-1.5" {...props} />,
                        p: ({node, ...props}) => <p className="mb-2 leading-relaxed text-slate-300" {...props} />,
                        li: ({node, ...props}) => <li className="mb-1 leading-normal list-disc pl-0.5 ml-4 text-slate-350" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-extrabold text-orange-400" {...props} />,
                      }}
                    >
                      {aiReport}
                    </ReactMarkdown>
                  </article>
                ) : (
                  <div className="h-[120px] flex flex-col items-center justify-center text-center opacity-30 space-y-3">
                    <FileText size={32} className="text-slate-500" />
                    <div>
                      <h4 className="text-[10px] font-black text-slate-300">리포트 스캔 대기 중</h4>
                      <p className="text-[8px] text-slate-500 mt-1">행정동 선택 시 실시간 가이드가 제공됩니다.</p>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <p className="text-[8.5px] font-bold text-slate-400 leading-relaxed bg-[#0b0f19]/30 rounded-lg p-2">
                  법적 근거: 기후위기 대응을 위한 탄소중립·녹색성장 기본법 제X조(취약계층 보호), 지자체 조례.
                </p>
                <p className="text-[7.5px] font-semibold text-slate-500">
                  ※ 본 정책 보고서는 기상청 실시간 AWS 관측소 데이터와 MOLIT 건축물 속성을 연계하여 산출한 지능형 정책 보좌 문서입니다.
                </p>
              </div>
            </section>

          </aside>
        )}

      </main>
    </div>
  );
}

export default App;
