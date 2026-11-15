import re
from typing import Tuple, Optional

# Escalation token specified in requirements
ESCALATE_TOKEN = "[ESCALATE]"

# English safety keywords and phrases (case-insensitive)
ENGLISH_SAFETY_KEYWORDS = [
    "self-harm",
    "self harm",
    "suicide",
    "suicidal",
    "hopeless",
    "hopelessness",
    "emergency",
    "kill myself",
    "end my life",
    "end it all",
    "want to end it all",
    "want to die",
    "can't go on",
    "cant go on",
    "no reason to live",
    "hang myself",
    "overdose",
    "hurt myself",
    "harming myself",
    "cutting myself",
]

# Arabic safety keywords and phrases
ARABIC_SAFETY_KEYWORDS = [
    "انتحار",
    "إيذاء النفس",
    "ايذاء النفس",
    "إيذاء نفسي",
    "قتل نفسي",
    "أموت",
    "اموت",
    "إنهاء حياتي",
    "انهاء حياتي",
    "أريد أن أموت",
    "اريد ان اموت",
    "يائس",
    "يائسة",
    "لا أمل",
    "لا امل",
    "طوارئ",
    "طوارئ طبية",
    "استسلمت",
    "الموت أهون",
    "لا فائدة من الحياة",
]


def detect_safety_keywords(text: str) -> Tuple[bool, Optional[str]]:
    """
    Check if user message contains critical crisis or self-harm keywords
    in either English or Arabic.
    Returns (True, matched_keyword) if found, else (False, None).
    """
    if not text:
        return False, None

    lower_text = text.lower()

    # Check English keywords
    for kw in ENGLISH_SAFETY_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lower_text):
            return True, kw

    # Check Arabic keywords (substring or word match)
    for kw in ARABIC_SAFETY_KEYWORDS:
        if kw in text:
            return True, kw

    return False, None


def parse_and_strip_escalate_token(text: str) -> Tuple[str, bool]:
    """
    Check if text contains the [ESCALATE] token.
    If present, strips the token, cleans whitespace, and returns (clean_text, True).
    Otherwise returns (text, False).
    """
    if not text:
        return "", False

    pattern = re.compile(r"\[ESCALATE\]", re.IGNORECASE)
    if pattern.search(text):
        cleaned = pattern.sub("", text)
        # Clean extra blank lines or double spaces left behind
        cleaned = re.sub(r" +", " ", cleaned).strip()
        return cleaned, True

    return text, False


def get_crisis_support_message(language: str = "en") -> str:
    """Calm supportive fallback message when immediate safety crisis is detected."""
    if language == "ar":
        return (
            "أنا أسمعك وأهتم بسلامتك جداً. سلامتك وصحتك النفسية هي أهم أولوياتنا هنا في المهمة. "
            "لقد قمت بإخطار الفريق الطبي المساعد والمراقبين الأرضيين فوراً لتقديم الدعم الكامل لك. "
            "أنت لست وحدك، وسنتجاوز هذا معاً خطوة بخطوة."
        )
    return (
        "I hear you, and your safety and well-being are our highest priority on this mission. "
        "I have immediately alerted flight surgery and ground medical support to coordinate "
        "direct support for you right now. You are not alone, and we are right here with you."
    )
