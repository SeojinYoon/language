#!/usr/bin/env python3
"""
==============================================================================
VocabMaster Configuration & Core Parameters (설정 및 핵심 파라미터)
==============================================================================
이 파일은 VocabMaster 애플리케이션의 모든 핵심 파라미터와 경로,
AI 모델 설정, 학습 세션 기준값 등을 한 곳에서 관리하는 중앙 설정 파일입니다.
환경 변수(OS Environment Variables)를 통해 동적으로 오버라이드할 수도 있습니다.
==============================================================================
"""

import os
import sys
from typing import List, Dict, Any

# ==============================================================================
# 1. 🎯 LEARNING GOALS & PROGRESS TARGETS (학습 목표 및 진행도 핵심 파라미터)
# ==============================================================================
# 🌟 [단어 맞추기 목표] 100% 진행도 달성 기준 단어 수 (기본값: 20)
# 사용자가 UI에서 수정하지 않고, 이 파라미터로 진행도 목표를 결정합니다.
# (예: 20으로 설정하면 20문제를 풀었을 때 진행도 100% 달성)
QUIZ_GOAL_TARGET: int = int(os.environ.get("QUIZ_GOAL_TARGET", 20))
DEFAULT_QUIZ_GOAL_TARGET: int = QUIZ_GOAL_TARGET  # 하위 호환 별칭

# 🌟 [일기 영작 목표] 100% 진행도 달성 기준 영작 대조 횟수 (기본값: 5)
# 사용자가 UI에서 수정하지 않고, 이 파라미터로 진행도 목표를 결정합니다.
# (예: 5로 설정하면 5회 영작 대조 완료 시 진행도 100% 달성)
DIARY_GOAL_TARGET: int = int(os.environ.get("DIARY_GOAL_TARGET", 5))

# 4지 선다 보기 개수
MULTIPLE_CHOICE_OPTIONS_COUNT: int = 4

# 게이미피케이션 경험치 및 보상 파라미터
XP_PER_CORRECT_ANSWER: int = 10
STREAK_BONUS_MULTIPLIER: int = 2
MAX_STREAK_BONUS_XP: int = 20

# 단어 숙련도 레벨 정의
MASTERY_LEVELS: Dict[int, str] = {
    1: "Hard (복습 필요)",
    2: "Good (학습 중)",
    3: "Easy (완전 숙련)"
}

# ==============================================================================
# 2. 📁 DIRECTORY & FILE PATHS (경로 설정)
# ==============================================================================
# 애플리케이션 루트 및 어휘 앱 디렉터리
VOCAB_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT: str = os.path.dirname(VOCAB_DIR)

# 원본 마크다운 단어장 경로
MARKDOWN_DISSIMILARITIES: str = os.path.join(PROJECT_ROOT, "English", "dissimilarities.md")
MARKDOWN_WORDS_ORGANIZED: str = os.path.join(PROJECT_ROOT, "English", "Words_organized.md")

# 프론트엔드 오프라인 캐시 및 번들 데이터 파일
DATA_JS_PATH: str = os.path.join(VOCAB_DIR, "data.js")
LOCAL_DIARY_JS_PATH: str = os.path.join(VOCAB_DIR, "local_diary.js")

# ⚙️ 기본 일기 CSV 경로 (개인정보 보호를 위해 Git 저장소 외부에 위치)
DEFAULT_DIARY_CSV_PATH: str = os.environ.get(
    "DIARY_CSV_PATH", 
    "/Users/seojin/mind.csv"
)

# ==============================================================================
# 3. 🌐 SERVER & NETWORK PARAMETERS (서버 및 네트워크 파라미터)
# ==============================================================================
# 웹 서버 포트 (CLI 인자 sys.argv[1] > 환경 변수 VOCAB_PORT > 기본값 3000)
DEFAULT_PORT: int = 3000
SERVER_PORT: int = int(os.environ.get("VOCAB_PORT", DEFAULT_PORT))
SERVER_HOST: str = os.environ.get("VOCAB_HOST", "0.0.0.0")

# 서버 실행 시 브라우저 자동 오픈 여부
AUTO_OPEN_BROWSER: bool = os.environ.get("VOCAB_AUTO_OPEN", "true").lower() in ("true", "1", "yes")

# ==============================================================================
# 4. 🤖 LOCAL GEMMA AI & ON-DEVICE INFERENCE (로컬 Gemma AI 설정)
# ==============================================================================
# 1순위: Edge Gallery 온디바이스 LiteRT 엔진 (Apple Metal GPU 가속)
LITERT_MODEL_SEARCH_PATTERNS: List[str] = [
    os.path.expanduser("~/Library/Containers/*/Data/Documents/Gemma_4_E2B_it/v0/*.litertlm"),
    os.path.expanduser("~/Library/Containers/F45A43A5-0F15-4C50-9D8A-998CB9F1B7CE/Data/Documents/Gemma_4_E2B_it/v0/gemma4_2b_v09_obfus_fix_all_modalities_thinking.litertlm")
]

# 온디바이스 LiteRT 추론 세부 파라미터
AI_MAX_OUTPUT_TOKENS: int = 900
AI_ENABLE_THINKING: bool = False
AI_THINKING_TOKEN_BUDGET: int = 0

# 2순위: 로컬 Ollama 백엔드 Fallback 설정
LOCAL_GEMMA_URL: str = os.environ.get("LOCAL_GEMMA_URL", "http://localhost:11434/api/generate")
LOCAL_GEMMA_MODEL: str = os.environ.get("LOCAL_GEMMA_MODEL", "gemma2:2b")
OLLAMA_TIMEOUT_SECONDS: int = 40

# AI 영작 첨삭 시스템 프롬프트 템플릿
AI_COACH_PROMPT_TEMPLATE: str = """당신은 영작 첨삭 코치입니다.
인사말, 서론, 원문 반복을 일체 생략하고, 기존 영문과의 차이점을 중심으로 아래 2가지 항목만 한국어로 명쾌하게 답변해주세요.
기존 영문에 대한 조언은 하지 말고, 사용자 영작에 대한 조언만 해주세요. 그리고 또, 한국어 원문, 사용자 영작, 기존 영문 전체 문단을 언급하지 마세요.

[한국어 원문] {korean}
[사용자 영작] {user_trans}
[기존 영문] {ref_trans}

1. 💡 기존 영문과의 뉘앙스 차이 (사용자 문장과 기존 영문의 핵심 어감/표현 차이)
2. 🚀 영어 실력 향상을 위한 조언 (더 자연스러운 영작을 위한 1~2가지 핵심 실전 팁)
"""

# ==============================================================================
# 5. 📔 DIARY CSV PARSING PARAMETERS (일기 파싱 파라미터)
# ==============================================================================
# CSV 인코딩 형식 (BOM 지원)
DIARY_CSV_ENCODING: str = "utf-8-sig"

# CSV 헤더 인식 기준 키워드
DIARY_HEADER_DATE_KEYWORD: str = "날짜"
DIARY_HEADER_CONTENT_KEYWORD: str = "내용"
DIARY_MIN_COLUMN_COUNT: int = 6

# 일기 항목 컬럼 매핑 인덱스
DIARY_COLUMN_INDEX = {
    "date": 0,
    "weather": 1,
    "type": 2,
    "mood": 3,
    "korean": 4,
    "english": 5,
    "reference": 6
}

# ==============================================================================
# 6. 🛠️ HELPER UTILITIES (설정 확인 및 진단 도구)
# ==============================================================================
def get_config_summary() -> Dict[str, Any]:
    """현재 설정 상태를 딕셔너리로 반환합니다."""
    import glob
    found_model = None
    for p in LITERT_MODEL_SEARCH_PATTERNS:
        matches = glob.glob(p)
        if matches and os.path.exists(matches[0]):
            found_model = matches[0]
            break

    csv_path = os.path.expanduser(DEFAULT_DIARY_CSV_PATH)

    return {
        "server": {
            "port": SERVER_PORT,
            "host": SERVER_HOST,
            "auto_open_browser": AUTO_OPEN_BROWSER
        },
        "paths": {
            "vocab_dir": VOCAB_DIR,
            "project_root": PROJECT_ROOT,
            "diary_csv_path": csv_path,
            "diary_csv_exists": os.path.exists(csv_path),
            "data_js_exists": os.path.exists(DATA_JS_PATH),
            "local_diary_js_exists": os.path.exists(LOCAL_DIARY_JS_PATH)
        },
        "ai_model": {
            "litert_ondevice_model": found_model or "Not Found (Edge Gallery 확인 필요)",
            "ollama_url": LOCAL_GEMMA_URL,
            "ollama_model": LOCAL_GEMMA_MODEL,
            "max_output_tokens": AI_MAX_OUTPUT_TOKENS
        },
        "quiz_parameters": {
            "quiz_goal_target": QUIZ_GOAL_TARGET,
            "choice_count": MULTIPLE_CHOICE_OPTIONS_COUNT,
            "xp_per_correct": XP_PER_CORRECT_ANSWER
        },
        "diary_parameters": {
            "diary_goal_target": DIARY_GOAL_TARGET
        }
    }

def print_config():
    """터미널에서 직접 실행 시 설정 현황을 깔끔하게 출력합니다."""
    summary = get_config_summary()
    print("=" * 68)
    print(" 🌟 VocabMaster Core Parameters & System Configuration 🌟")
    print("=" * 68)
    print(f"📡 Server Port         : {summary['server']['port']} ({summary['server']['host']})")
    print(f"📔 Diary CSV Path      : {summary['paths']['diary_csv_path']}")
    print(f"   └ File Exists?      : {'✅ YES' if summary['paths']['diary_csv_exists'] else '❌ NOT FOUND'}")
    print(f"🤖 On-Device AI Model  : {summary['ai_model']['litert_ondevice_model']}")
    print(f"🦙 Ollama Fallback     : {summary['ai_model']['ollama_url']} ({summary['ai_model']['ollama_model']})")
    print(f"🎯 Quiz Goal Target    : {summary['quiz_parameters']['quiz_goal_target']} 단어 (100% 진행도 완료 기준 파라미터)")
    print(f"📔 Diary Goal Target   : {summary['diary_parameters']['diary_goal_target']}회 번역 (100% 진행도 완료 기준 파라미터)")
    print(f"⭐ Base XP Per Word    : +{summary['quiz_parameters']['xp_per_correct']} XP")
    print("=" * 68)

if __name__ == "__main__":
    print_config()
