import { useState } from "react";
import { 
  MapPin, Star, Sparkles, ShieldCheck, Send, ChevronRight, Heart, 
  BadgeCheck, Calendar, DollarSign, CheckCircle, Clock, Users, 
  Camera, Music, Utensils, Gift, MessageSquare, Bell, Settings,
  ArrowLeft, Plus, Minus, Filter, Search, ChevronDown, Zap,
  TrendingUp, AlertTriangle, Target, PieChart, BarChart3, Calculator,
  User, Wallet, PiggyBank
} from "lucide-react";

const vendors = [
  {
    id: "H1001",
    name: "호텔 루미에르",
    type: "웨딩홀",
    price: "2,950만원",
    priceNum: 29500000,
    seat: "200석",
    rating: 4.6,
    reviews: 128,
    perks: ["원본 제공", "주차 300대", "야간가든"],
    image: "🏛️",
    location: "강남구",
    description: "유럽 클래식 스타일의 럭셔리 웨딩홀",
    savings: "230만원 절약 가능"
  },
  {
    id: "S2001", 
    name: "스튜디오 노바",
    type: "스튜디오",
    price: "350만원",
    priceNum: 3500000,
    seat: "촬영 3컨셉",
    rating: 4.8,
    reviews: 96,
    perks: ["원본 제공", "야외 촬영", "드레스 대여"],
    image: "📸",
    location: "성수동",
    description: "자연광이 아름다운 감성 스튜디오",
    savings: "80만원 절약 가능"
  },
  {
    id: "D3001",
    name: "아틀리에 클레르",
    type: "드레스",
    price: "500만원", 
    priceNum: 5000000,
    seat: "피팅 3회",
    rating: 4.7,
    reviews: 82,
    perks: ["신상 라인", "수제 베일", "맞춤 수선"],
    image: "👗",
    location: "청담동",
    description: "파리 컬렉션 브랜드 드레스 전문",
    savings: "150만원 절약 가능"
  }
];

const timelineItems = [
  { id: 1, title: "예식장 예약", date: "2025-03-15", status: "completed", category: "venue" },
  { id: 2, title: "드레스 피팅", date: "2025-04-20", status: "upcoming", category: "dress" },
  { id: 3, title: "스튜디오 촬영", date: "2025-05-10", status: "pending", category: "photo" },
  { id: 4, title: "청첩장 발송", date: "2025-06-01", status: "pending", category: "invitation" },
  { id: 5, title: "결혼식", date: "2025-07-15", status: "pending", category: "wedding" }
];

const budgetCategories = [
  { name: "웨딩홀", budget: 3000, spent: 2950, color: "#C8A96A" },
  { name: "스튜디오", budget: 400, spent: 350, color: "#23C19C" },
  { name: "드레스", budget: 600, spent: 500, color: "#FF6B6B" },
  { name: "메이크업", budget: 200, spent: 0, color: "#845EC2" },
  { name: "플라워", budget: 150, spent: 0, color: "#FF9671" }
];

// 예시 체크리스트 데이터 (홈 화면용)
const checklistItems = [
  { id: 1, text: "청첩장 시안 확인", checked: false },
  { id: 2, text: "하객 명단 정리 시작", checked: true },
  { id: 3, text: "스튜디오 촬영 컨셉 확정", checked: false },
  { id: 4, text: "신혼여행지 항공권 예약", checked: false },
];

const latestTips = [
  { id: 1, title: "웨딩홀 계약 시 꼭 체크해야 할 10가지", date: "2025.09.10" },
  { id: 2, title: "스드메 비용 200% 절약하는 꿀팁", date: "2025.09.08" },
  { id: 3, title: "하객선물을 위한 센스 있는 답례품 추천", date: "2025.09.05" },
];


// D-Day 계산 함수
const calculateDday = (weddingDate) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const wedding = new Date(weddingDate);
  const diffTime = wedding.getTime() - today.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays > 0 ? diffDays : 0;
};

// 다음 일정 찾기
const getNextEvent = () => {
  const nextEvent = timelineItems
    .filter(item => item.status === 'upcoming' || item.status === 'pending')
    .sort((a, b) => new Date(a.date) - new Date(b.date))[0];
  return nextEvent;
};

// 예산 총액 계산
const totalBudget = budgetCategories.reduce((sum, category) => sum + category.budget, 0);
const totalSpent = budgetCategories.reduce((sum, category) => sum + category.spent, 0);
const budgetPercentage = (totalSpent / totalBudget) * 100;
const budgetRemainder = totalBudget - totalSpent;

// 도넛 차트 SVG
const DonutChart = ({ percentage, color, radius = 50, strokeWidth = 10 }) => {
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  return (
    <svg width={radius * 2 + strokeWidth} height={radius * 2 + strokeWidth} className="transform -rotate-90">
      <circle
        cx={radius + strokeWidth / 2}
        cy={radius + strokeWidth / 2}
        r={radius}
        fill="none"
        stroke="#E5E7EB"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={radius + strokeWidth / 2}
        cy={radius + strokeWidth / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
        className="transition-all duration-1000 ease-in-out"
      />
    </svg>
  );
};


export default function MarryRouteApp() {
  const [currentView, setCurrentView] = useState('chat');
  const [chatMessages, setChatMessages] = useState([
    { id: 1, from: 'bot', content: '안녕하세요! 저는 AI 웨딩 플래너 마리예요 ✨ 어떤 도움이 필요하신가요?' },
  ]);
  const [newMessage, setNewMessage] = useState('');
  const [categoryDropdown, setCategoryDropdown] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('전체');
  const [localChecklist, setLocalChecklist] = useState(checklistItems);

  const theme = {
    bg: "bg-gradient-to-br from-yellow-50 via-white to-amber-50",
    text: "text-amber-900",
    subtext: "text-amber-700",
    accent: "#C8A96A",
    accentLight: "#F5F1E8",
    primary: "bg-amber-600 hover:bg-amber-700 text-white",
    secondary: "bg-white hover:bg-amber-50 text-amber-900 border border-amber-200",
    card: "bg-white/90 backdrop-blur border border-amber-200/50"
  };

  const categories = [
    '전체', '웨딩홀', '스튜디오', '드레스샵', '메이크업', 
    '한복', '결혼 반지', '예물', '답례품', '혼수', '청첩장 모임', '신혼여행'
  ];

  const availableCategories = ['웨딩홀', '스튜디오', '드레스샵', '메이크업'];

  const handleCategorySelect = (category) => {
    setSelectedCategory(category);
    setCategoryDropdown(false);
  };

  const filteredVendors = selectedCategory === '전체' 
    ? vendors 
    : vendors.filter(vendor => {
        const categoryMap = {
          '웨딩홀': '웨딩홀',
          '스튜디오': '스튜디오', 
          '드레스샵': '드레스',
          '메이크업': '메이크업'
        };
        return vendor.type === categoryMap[selectedCategory];
      });

  const sendMessage = () => {
    if (!newMessage.trim()) return;
    
    const userMessage = { id: Date.now(), from: 'user', content: newMessage };
    setChatMessages(prev => [...prev, userMessage]);
    
    setTimeout(() => {
      const responses = [
        '네, 그 부분 도와드릴게요! 예산과 선호도를 알려주시면 더 정확한 추천을 해드릴 수 있어요.',
        '좋은 선택이에요! 해당 업체의 상세 정보와 리뷰를 확인해보시겠어요?',
        '이런 점도 고려해보세요: 계약 조건, 취소 정책, 추가 비용 등을 꼼꼼히 확인하시는 것이 좋아요.',
        '현재 진행 상황을 체크해드릴게요. 다음 단계는 이렇게 진행하시면 됩니다!'
      ];
      const botMessage = { 
        id: Date.now() + 1, 
        from: 'bot', 
        content: responses[Math.floor(Math.random() * responses.length)]
      };
      setChatMessages(prev => [...prev, botMessage]);
    }, 1000);
    
    setNewMessage('');
  };

  const handleQuickAction = (action) => {
    const userMessage = { id: Date.now(), from: 'user', content: action };
    setChatMessages(prev => [...prev, userMessage]);
    setTimeout(() => {
      const botMessage = { 
        id: Date.now() + 1, 
        from: 'bot', 
        content: `${action}에 대해 자세히 설명해드릴게요! 어떤 부분이 가장 궁금하신가요?` 
      };
      setChatMessages(prev => [...prev, botMessage]);
    }, 1000);
  };
  
  const handleChecklistItemToggle = (id) => {
    setLocalChecklist(prev => 
      prev.map(item => 
        item.id === id ? { ...item, checked: !item.checked } : item
      )
    );
  };

  const weddingDate = '2025-07-15';
  const dDay = calculateDday(weddingDate);
  const nextEvent = getNextEvent();

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} antialiased transition-all duration-500`}>
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-white/80 border-b border-gray-100">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`h-8 w-8 rounded-full flex items-center justify-center text-white transition-all duration-300`} style={{ backgroundColor: theme.accent }}>
                <MapPin className="h-4 w-4" />
              </div>
              <span className="font-bold text-xl">MarryRoute</span>
              <span className={`ml-2 text-xs rounded-full px-2 py-1 flex items-center gap-1 ${theme.secondary} transition-all duration-300`}>
                <Sparkles className="h-3 w-3" />
                마리
              </span>
            </div>
            
            <div className="flex items-center gap-4">
              <button 
                className={`p-2 rounded-xl transition-all duration-300 hover:scale-110 relative group`}
                style={{ backgroundColor: theme.accentLight }}
                title="MY 페이지"
              >
                <User className="h-5 w-5" style={{ color: theme.accent }} />
                <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full transition-all duration-300`}
                     style={{ backgroundColor: theme.accent }}>
                  <div className="w-full h-full rounded-full bg-white opacity-50 animate-pulse"></div>
                </div>
                
                {/* 툴팁 */}
                <div className="absolute -bottom-12 left-1/2 transform -translate-x-1/2 px-3 py-1 bg-black/80 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 whitespace-nowrap">
                  MY 페이지 (준비중)
                  <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-black/80 rotate-45"></div>
                </div>
              </button>
              
              <button className="p-2 rounded-xl hover:bg-gray-100 transition-colors relative">
                <Bell className="h-5 w-5" />
                {/* 알림 뱃지 */}
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
                  <span className="text-xs text-white font-bold">3</span>
                </div>
              </button>
              
              <button className="p-2 rounded-xl hover:bg-gray-100 transition-colors">
                <Settings className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8 pb-28">
        {currentView === 'home' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* D-Day & Next Event */}
            <button 
              onClick={() => setCurrentView('timeline')}
              className={`w-full ${theme.card} rounded-3xl p-8 shadow-xl relative overflow-hidden text-left transition-all duration-500 hover:scale-[1.02] active:scale-[0.98]`}
            >
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-current opacity-5 rounded-full transform translate-x-16 -translate-y-16" />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-4">
                  <div className={`h-12 w-12 rounded-full flex items-center justify-center text-white transition-all duration-300`} style={{ backgroundColor: theme.accent }}>
                    <Calendar className="h-6 w-6" />
                  </div>
                  <div className="font-semibold text-xl">결혼식까지 남은 시간</div>
                </div>
                <div className="text-5xl font-extrabold mb-2 text-transparent bg-clip-text bg-gradient-to-r from-amber-600 to-amber-900 transition-all duration-300">
                  D-{dDay}
                </div>
                {nextEvent && (
                  <div className={`text-lg font-medium ${theme.subtext} transition-colors duration-300`}>
                    다음 일정: {nextEvent.title} ({nextEvent.date})
                  </div>
                )}
                <div className="absolute top-8 right-8 text-amber-500 opacity-20">
                  <ChevronRight className="h-10 w-10" />
                </div>
              </div>
            </button>

            {/* Budget & Progress */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <button 
                onClick={() => setCurrentView('budget')}
                className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-500 hover:shadow-lg hover:scale-105 active:scale-[0.98] text-left`}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-lg">예산 현황</h3>
                  <PiggyBank className="h-6 w-6 opacity-60" />
                </div>
                <div className="flex items-center justify-center relative my-4">
                  <DonutChart percentage={budgetPercentage} color={theme.accent} />
                  <div className="absolute text-center">
                    <div className="text-2xl font-bold">{Math.round(budgetPercentage)}%</div>
                    <div className="text-sm opacity-60">사용</div>
                  </div>
                </div>
                <div className={`text-sm ${theme.subtext} text-center transition-colors duration-300`}>
                  총 {totalBudget.toLocaleString()}만원 중 {totalSpent.toLocaleString()}만원 사용
                </div>
              </button>

              <button 
                onClick={() => setCurrentView('timeline')}
                className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-500 hover:shadow-lg hover:scale-105 active:scale-[0.98] text-left`}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-lg">진행률</h3>
                  <BarChart3 className="h-6 w-6 opacity-60" />
                </div>
                <div className="text-5xl font-bold text-green-600 my-4">
                  60%
                </div>
                <div className={`text-sm font-medium ${theme.subtext} transition-colors duration-300`}>
                  126일 남았고, 순조롭게 진행중!
                </div>
              </button>
            </div>

            {/* AI Recommended Vendors */}
            <div className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-xl">✨ AI 추천 업체</h3>
                <button 
                  onClick={() => setCurrentView('search')}
                  className={`flex items-center text-sm font-medium transition-colors duration-300 hover:text-amber-600`}
                >
                  <ChevronRight className="h-5 w-5" />
                  더보기
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {vendors.slice(0, 3).map((vendor, i) => (
                  <button 
                    key={vendor.id}
                    onClick={() => setCurrentView('search')}
                    className="w-full text-left p-4 rounded-xl bg-white/50 backdrop-blur-sm hover:bg-white/80 transition-all duration-300 hover:scale-105 cursor-pointer shadow-sm"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className="text-2xl">{vendor.image}</div>
                      <div>
                        <div className="font-semibold text-lg leading-tight">{vendor.name}</div>
                        <div className={`text-sm ${theme.subtext} leading-tight`}>{vendor.type}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 mb-2">
                      <Star className="h-4 w-4 text-yellow-500 fill-current" />
                      <span className="text-sm font-medium">{vendor.rating}</span>
                      <span className={`text-xs ${theme.subtext}`}>({vendor.reviews})</span>
                    </div>
                    <div className="text-lg font-bold">{vendor.price}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Checklist */}
            <div className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-xl">✅ 진행 중인 체크리스트</h3>
                <button 
                  onClick={() => setCurrentView('timeline')}
                  className={`flex items-center text-sm font-medium transition-colors duration-300 hover:text-amber-600`}
                >
                  <ChevronRight className="h-5 w-5" />
                  전체 보기
                </button>
              </div>
              <div className="space-y-4">
                {localChecklist.map((item) => (
                  <div key={item.id} className="flex items-center justify-between p-4 bg-gray-50/50 rounded-xl transition-all duration-300 hover:bg-gray-100">
                    <label className="flex items-center gap-4 cursor-pointer">
                      <input 
                        type="checkbox"
                        checked={item.checked}
                        onChange={() => handleChecklistItemToggle(item.id)}
                        className={`h-6 w-6 rounded-full transition-all duration-300 accent-amber-600`}
                      />
                      <span className={`font-medium ${item.checked ? 'text-gray-500 line-through' : ''}`}>
                        {item.text}
                      </span>
                    </label>
                    <ChevronRight className={`h-5 w-5 ${theme.subtext}`} />
                  </div>
                ))}
              </div>
            </div>

            {/* Latest Tips & Community */}
            <div className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-xl">💡 최신 꿀팁</h3>
                <button className={`flex items-center text-sm font-medium transition-colors duration-300 hover:text-amber-600`}>
                  <ChevronRight className="h-5 w-5" />
                  더보기
                </button>
              </div>
              <div className="space-y-4">
                {latestTips.map((tip, i) => (
                  <div key={tip.id} className="flex items-start gap-4 p-4 bg-gray-50/50 rounded-xl transition-all duration-300 hover:bg-gray-100 cursor-pointer">
                    <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-amber-100/50">
                      <Zap className={`h-5 w-5`} style={{ color: theme.accent }} />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">{tip.title}</div>
                      <div className={`text-sm ${theme.subtext}`}>{tip.date}</div>
                    </div>
                    <ChevronRight className={`h-5 w-5 ${theme.subtext}`} />
                  </div>
                ))}
              </div>
            </div>
            
          </div>
        )}

        {currentView === 'search' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className={`${theme.card} rounded-2xl p-4 mb-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold">AI 추천 업체</h2>
                <button 
                  onClick={() => setCurrentView('chat')}
                  className={`px-4 py-2 text-sm font-medium rounded-xl transition-all duration-300 hover:scale-105 flex items-center gap-2 ${theme.primary}`}
                >
                  <Sparkles className="h-4 w-4" />
                  마리에게 추천 받기
                </button>
              </div>
            </div>
            
            {/* Category Dropdown */}
            <div className="relative mb-6">
              <button 
                onClick={() => setCategoryDropdown(!categoryDropdown)}
                className={`w-full ${theme.secondary} px-4 py-3 rounded-xl font-semibold flex items-center justify-between hover:scale-105 transition-all duration-300`}
              >
                <span>{selectedCategory}</span>
                <ChevronDown className={`h-5 w-5 transition-transform duration-300 ${categoryDropdown ? 'rotate-180' : ''}`} />
              </button>
              
              {categoryDropdown && (
                <div className={`absolute top-full left-0 right-0 mt-2 ${theme.card} rounded-xl shadow-lg z-10 max-h-64 overflow-y-auto`}>
                  {categories.map((category, index) => (
                    <button
                      key={category}
                      onClick={() => handleCategorySelect(category)}
                      className={`w-full px-4 py-3 text-left hover:bg-amber-50 transition-colors ${
                        selectedCategory === category ? 'bg-amber-100 font-semibold' : ''
                      } ${index === 0 ? 'rounded-t-xl' : ''} ${index === categories.length - 1 ? 'rounded-b-xl' : ''}`}
                    >
                      {category}
                      {!availableCategories.includes(category) && category !== '전체' && (
                        <span className="ml-2 text-xs text-gray-500">(준비중)</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            {/* Search and Filter */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="업체명이나 지역으로 검색..."
                  className="w-full pl-12 pr-4 py-3 rounded-xl border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-300 bg-white"
                />
              </div>
              <button className={`${theme.secondary} px-4 py-3 rounded-xl font-semibold flex items-center justify-center gap-2 hover:scale-105 transition-all duration-300`}>
                <Filter className="h-5 w-5" />
                필터
              </button>
            </div>

            {/* AI 추천 업체 */}
            <div className="animate-in slide-in-from-bottom duration-700">
              {selectedCategory !== '전체' && !availableCategories.includes(selectedCategory) ? (
                <div className={`${theme.card} rounded-2xl p-12 shadow-sm text-center`}>
                  <div className="text-6xl mb-4">🚧</div>
                  <h3 className="text-xl font-bold mb-2">서비스 준비 중</h3>
                  <p className={`${theme.subtext} mb-6`}>
                    {selectedCategory} 서비스는 현재 준비 중입니다.<br />
                    빠른 시일 내에 만나뵐 수 있도록 노력하겠습니다.
                  </p>
                  <button 
                    onClick={() => setCurrentView('chat')}
                    className={`${theme.primary} px-6 py-3 rounded-xl font-semibold flex items-center gap-2 mx-auto transition-all duration-300 hover:scale-105`}
                  >
                    <MessageSquare className="h-5 w-5" />
                    마리에게 문의하기
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredVendors.map((vendor, i) => (
                    <div 
                      key={vendor.id}
                      className={`${theme.card} rounded-2xl p-6 shadow-sm hover:shadow-lg transition-all duration-300 hover:scale-105`}
                      style={{ animationDelay: `${i * 100}ms` }}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="text-3xl">{vendor.image}</div>
                        <div className={`text-xs px-2 py-1 rounded-full font-medium transition-all duration-300`} style={{ backgroundColor: theme.accentLight, color: theme.accent }}>
                          TOP {i + 1}
                        </div>
                      </div>
                      
                      <h4 className="font-bold text-lg mb-1">{vendor.name}</h4>
                      <p className={`text-sm mb-3 ${theme.subtext} transition-colors duration-300`}>{vendor.description}</p>
                      
                      <div className="flex items-center gap-2 mb-3">
                        <Star className="h-4 w-4 text-yellow-500 fill-current" />
                        <span className="text-sm font-medium">{vendor.rating}</span>
                        <span className={`text-xs ${theme.subtext} transition-colors duration-300`}>({vendor.reviews} 리뷰)</span>
                      </div>
                      
                      <div className="flex items-center justify-between mb-4">
                        <span className="font-bold text-lg">{vendor.price}</span>
                        <span className="text-sm text-green-600">{vendor.savings}</span>
                      </div>
                      
                      <div className="flex flex-wrap gap-2 mb-4">
                        {vendor.perks.slice(0, 2).map(perk => (
                          <span key={perk} className={`text-xs px-2 py-1 rounded-full ${theme.secondary} transition-all duration-300`}>
                            {perk}
                          </span>
                        ))}
                      </div>
                      
                      <div className="flex gap-2">
                        <button className={`flex-1 ${theme.primary} px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 hover:scale-105`}>
                          상세보기
                        </button>
                        <button className={`p-2 ${theme.secondary} rounded-xl transition-all duration-300 hover:scale-110`}>
                          <Heart className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {currentView === 'timeline' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className={`${theme.card} rounded-2xl p-4 mb-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold">결혼 준비 타임라인</h2>
                <button 
                  onClick={() => setCurrentView('chat')}
                  className={`px-4 py-2 text-sm font-medium rounded-xl transition-all duration-300 hover:scale-105 flex items-center gap-2 ${theme.primary}`}
                >
                  <Sparkles className="h-4 w-4" />
                  일정 조율 with 마리
                </button>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4 mb-6">
              <button className={`${theme.primary} px-4 py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all duration-300 hover:scale-105`}>
                <Plus className="h-5 w-5" />
                일정 추가
              </button>
              <button className={`${theme.secondary} px-4 py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all duration-300 hover:scale-105`}>
                <Minus className="h-5 w-5" />
                일정 삭제
              </button>
            </div>
            
            <div className="space-y-4">
              {timelineItems.map((item, i) => (
                <div 
                  key={item.id}
                  className={`${theme.card} rounded-2xl p-6 shadow-sm relative transition-all duration-300 hover:shadow-lg`}
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 ${
                      item.status === 'completed' ? 'bg-green-500' :
                      item.status === 'upcoming' ? `text-white` : 'bg-gray-300'
                    }`} style={item.status === 'upcoming' ? { backgroundColor: theme.accent } : {}}>
                      {item.status === 'completed' ? (
                        <CheckCircle className="h-6 w-6 text-white" />
                      ) : (
                        <Clock className="h-6 w-6 text-white" />
                      )}
                    </div>
                    
                    <div className="flex-1">
                      <h4 className="font-semibold text-lg">{item.title}</h4>
                      <p className={`${theme.subtext} transition-colors duration-300`}>{item.date}</p>
                    </div>
                    
                    <div className={`px-3 py-1 rounded-full text-sm font-medium transition-all duration-300 ${
                      item.status === 'completed' ? 'bg-green-100 text-green-700' :
                      item.status === 'upcoming' ? 'text-white' : 'bg-gray-100 text-gray-700'
                    }`} style={item.status === 'upcoming' ? { backgroundColor: theme.accentLight, color: theme.accent } : {}}>
                      {item.status === 'completed' ? '완료' :
                       item.status === 'upcoming' ? '진행중' : '예정'}
                    </div>
                  </div>
                  
                  {item.status === 'upcoming' && (
                    <div className="mt-4 flex gap-2">
                      <button className={`${theme.primary} px-4 py-2 rounded-xl text-sm transition-all duration-300 hover:scale-105`}>
                        진행하기
                      </button>
                      <button className={`${theme.secondary} px-4 py-2 rounded-xl text-sm transition-all duration-300 hover:scale-105`}>
                        일정 변경
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {currentView === 'budget' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className={`${theme.card} rounded-2xl p-4 mb-6 shadow-sm transition-all duration-300`}>
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold">예산 관리</h2>
                <button 
                  onClick={() => setCurrentView('chat')}
                  className={`px-4 py-2 text-sm font-medium rounded-xl transition-all duration-300 hover:scale-105 flex items-center gap-2 ${theme.primary}`}
                >
                  <Sparkles className="h-4 w-4" />
                  예산 관리 with 마리
                </button>
              </div>
            </div>
            
            <div className={`${theme.card} rounded-2xl p-6 shadow-sm transition-all duration-300`}>
              <h3 className="text-lg font-semibold mb-4">전체 예산 현황</h3>
              <div className="grid grid-cols-2 gap-6 mb-6">
                <div>
                  <div className="text-3xl font-bold mb-2">{totalSpent.toLocaleString()}만원</div>
                  <div className={`${theme.subtext} transition-colors duration-300`}>총 사용액</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-green-600 mb-2">{budgetRemainder.toLocaleString()}만원</div>
                  <div className={`${theme.subtext} transition-colors duration-300`}>잔여 예산</div>
                </div>
              </div>
              
              <div className="mb-6">
                <button className={`w-full ${theme.primary} px-4 py-3 rounded-xl font-semibold transition-all duration-300 hover:scale-105`}>
                  예산 수정
                </button>
              </div>
              
              <div className="space-y-4">
                {budgetCategories.map((category, i) => {
                  const percentage = (category.spent / category.budget) * 100;
                  return (
                    <div key={category.name} className="space-y-2" style={{ animationDelay: `${i * 100}ms` }}>
                      <div className="flex justify-between items-center">
                        <span className="font-medium">{category.name}</span>
                        <span className="text-sm">
                          {category.spent}만원 / {category.budget}만원
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div 
                          className="h-3 rounded-full transition-all duration-1000"
                          style={{ 
                            backgroundColor: category.color, 
                            width: `${Math.min(percentage, 100)}%` 
                          }}
                        />
                      </div>
                      {percentage > 90 && (
                        <div className="flex items-center gap-1 text-orange-600 text-sm">
                          <AlertTriangle className="h-4 w-4" />
                          예산 초과 위험
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {currentView === 'chat' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className={`${theme.card} rounded-3xl shadow-xl flex flex-col h-[650px] overflow-hidden transition-all duration-300`}>
              {/* Chat Header */}
              <div className="relative px-6 py-5 border-b border-gray-100/50 bg-gradient-to-r from-white/50 to-transparent">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white shadow-lg transition-all duration-300`} 
                         style={{ backgroundColor: theme.accent }}>
                      <Sparkles className="h-6 w-6" />
                    </div>
                    <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white animate-pulse"></div>
                  </div>
                  <div className="flex-1">
                    <div className="font-bold text-lg">마리</div>
                    <div className={`text-sm ${theme.subtext} flex items-center gap-2 transition-colors duration-300`}>
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                      AI 웨딩 플래너 • 실시간 상담
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gradient-to-b from-transparent to-gray-50/30">
                {chatMessages.map((message, index) => (
                  <div
                    key={message.id}
                    className={`flex ${message.from === 'user' ? 'justify-end' : 'justify-start'} items-end gap-2 animate-in slide-in-from-bottom duration-300`}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    {message.from === 'bot' && (
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-sm shadow-md mb-1 transition-all duration-300`} 
                           style={{ backgroundColor: theme.accent }}>
                        ✨
                      </div>
                    )}
                    
                    <div className={`max-w-sm lg:max-w-md ${
                      message.from === 'user' 
                        ? 'text-white shadow-lg' 
                        : `text-gray-800 shadow-md border transition-all duration-300`
                    } rounded-3xl px-5 py-4 relative`} 
                    style={message.from === 'user' ? {
                      backgroundColor: theme.accent
                    } : {
                      backgroundColor: theme.accentLight, 
                      borderColor: '#E8DCC8' 
                    }}>
                      
                      <div className="text-sm leading-relaxed">{message.content}</div>
                      
                      {message.from === 'bot' && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button className="text-xs px-3 py-2 bg-white rounded-xl hover:bg-gray-50 transition-colors shadow-sm font-medium">
                            👍 도움됨
                          </button>
                          <button className="text-xs px-3 py-2 bg-white rounded-xl hover:bg-gray-50 transition-colors shadow-sm font-medium">
                            📋 더 알아보기
                          </button>
                        </div>
                      )}
                      
                      <div className={`text-xs mt-2 ${message.from === 'user' ? 'text-gray-300' : 'text-gray-500'}`}>
                        방금 전
                      </div>
                    </div>
                    
                    {message.from === 'user' && (
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-sm shadow-md mb-1`}
                          style={{ backgroundColor: theme.accent }}>
                        👤
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              {/* Quick Actions */}
              <div className="px-6 py-3 border-t border-gray-100/50">
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {['예산 상담', '업체 추천', '일정 조정', '계약서 검토', '꿀팁 공유'].map(action => (
                    <button
                      key={action}
                      onClick={() => handleQuickAction(action)}
                      className={`flex-shrink-0 px-4 py-2 text-xs font-medium rounded-xl transition-all duration-300 ${theme.secondary} hover:scale-105`}
                    >
                      {action}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Input */}
              <div className="px-6 py-4 bg-white/50 backdrop-blur-sm">
                <div className="flex gap-3 items-end">
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                      placeholder="마리에게 궁금한 것을 물어보세요..."
                      className="w-full px-5 py-3 pr-12 rounded-2xl border border-gray-200 focus:outline-none focus:ring-2 focus:border-transparent bg-white shadow-sm text-sm transition-all duration-300"
                      style={{ focusRingColor: theme.accent }}
                    />
                    <button className="absolute right-3 top-1/2 transform -translate-y-1/2 p-1 rounded-lg hover:bg-gray-100 transition-colors">
                      <Plus className="h-4 w-4 text-gray-400" />
                    </button>
                  </div>
                  <button 
                    onClick={sendMessage}
                    disabled={!newMessage.trim()}
                    className={`p-3 rounded-2xl font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed shadow-lg transition-all duration-300 hover:scale-105 active:scale-95`}
                    style={{ backgroundColor: theme.accent }}
                  >
                    <Send className="h-5 w-5" />
                  </button>
                </div>
                
                <div className="mt-2 text-xs text-gray-500 text-center">
                  마리는 AI로, 실제 계약 전 전문가 상담을 권장합니다
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-6 py-3">
          <div className="flex justify-around">
            {[
              { id: 'chat', icon: MessageSquare, label: '마리' },
              { id: 'timeline', icon: Calendar, label: '일정' },
              { id: 'home', icon: MapPin, label: '홈' },
              { id: 'search', icon: Search, label: '찾기' },
              { id: 'budget', icon: PiggyBank, label: '예산' }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setCurrentView(item.id)}
                className={`flex flex-col items-center gap-1 py-2 px-4 rounded-xl transition-all duration-300 ${
                  currentView === item.id 
                    ? `text-white scale-110`
                    : `${theme.subtext} hover:bg-gray-100 hover:scale-105`
                }`}
                style={currentView === item.id ? { backgroundColor: theme.accent } : {}}
              >
                <item.icon className="h-5 w-5" />
                <span className="text-xs font-medium">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>
    </div>
  );
}