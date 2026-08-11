import httpx
import json
import logging
import random
import re
import string
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an expert social media content creator. Given a description of media (image, video, or text), generate optimized social media content.

You MUST respond with ONLY valid JSON (no markdown, no code fences) matching this exact structure:
{
  "caption": "An engaging social media caption",
  "long_caption": "A detailed, storytelling caption with 3-5 sentences for Instagram carousel or detailed posts",
  "short_caption": "A punchy 1-2 line caption for quick posts and stories",
  "funny_caption": "A humorous, witty caption that drives engagement",
  "professional_caption": "A polished, brand-safe caption for business use",
  "travel_caption": "A wanderlust-inspiring caption for travel content",
  "business_caption": "A B2B or entrepreneurial caption for business content",
  "food_caption": "A mouth-watering caption optimized for food content",
  "luxury_caption": "An elegant, aspirational caption for premium content",
  "carousel_text": "Text slide content for a 5-slide carousel post (separate slides with |||)",
  "thumbnail_text": "Bold 3-6 word text overlay for a video thumbnail",
  "alt_text": "Accessibility description of the visual content for screen readers",
  "hashtags": "#relevant #hashtags #here",
  "keywords": "keyword1, keyword2, keyword3",
  "emojis": "relevant emoji string",
  "cta": "A compelling call to action",
  "hook": "An attention-grabbing hook line",
  "reel_title": "A catchy title for a short-form reel or TikTok (max 60 chars)",
  "seo_tags": "seo, tags, for, discoverability",
  "summary": "A brief 1-2 sentence summary of the content",
  "viral_score": 0,
  "viral_score_reason": "Brief explanation for the viral score rating"
}

For viral_score: rate the content's viral potential from 1-100 based on engagement factors like hook strength, emotional appeal, trendiness, shareability, and visual interest. Provide a short rationale in viral_score_reason.

Be creative, platform-aware, and optimize for engagement. Make captions punchy and hashtags trending where appropriate."""

TRENDING_HASHTAGS = [
    "#contentcreator", "#socialmediatips", "#viral", "#trending",
    "#explorepage", "#instagood", "#photooftheday", "#content",
    "#marketing", "#digitalmarketing", "#socialmedia", "#reels",
    "#fyp", "#viralcontent", "#growthhacking", "#engagement",
]

CTA_OPTIONS = [
    "Double tap if you agree!",
    "Drop a comment below!",
    "Share with someone who needs this!",
    "Tag a friend!",
    "Save this for later!",
    "Follow for more content like this!",
    "What do you think? Let us know!",
    "Like & share for more!",
]

HOOK_TEMPLATES = [
    "Wait for it... ",
    "You won't believe what happens next!",
    "This changes everything about {topic}!",
    "POV: You just discovered {topic}",
    "The secret nobody tells you about {topic}",
    "Stop scrolling - you need to see this!",
    "Here's the truth about {topic}...",
    "3 things I wish I knew about {topic} earlier",
]


def _extract_keywords_from_text(text: str) -> list[str]:
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    stop_words = {
        'this', 'that', 'with', 'from', 'your', 'about', 'have', 'been',
        'were', 'they', 'their', 'would', 'could', 'should', 'will',
        'just', 'also', 'more', 'some', 'than', 'them', 'then', 'what',
        'when', 'make', 'like', 'into', 'over', 'such', 'only', 'other',
    }
    keywords = [w for w in words if w not in stop_words]
    if len(keywords) < 3:
        keywords.extend(["content", "social", "media", "creative", "trending"])
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:8]


def _fallback_generate_content(description: str) -> dict:
    clean_text = description
    marker = "Text input for social media content creation:\n\n"
    if marker in clean_text:
        clean_text = clean_text.split(marker)[-1]
    marker2 = "Analyze this content description and generate social media posts:\n\n"
    if marker2 in clean_text:
        clean_text = clean_text.split(marker2)[-1]
    clean_text = clean_text.strip()
    if not clean_text:
        clean_text = description
    keywords = _extract_keywords_from_text(clean_text)
    topic = "this" if not keywords else keywords[0]
    selected_hashtags = random.sample(TRENDING_HASHTAGS, min(6, len(TRENDING_HASHTAGS)))
    for kw in keywords[:3]:
        tag = f"#{kw.replace(' ', '')}"
        if tag not in selected_hashtags:
            selected_hashtags.append(tag)
    hook = random.choice(HOOK_TEMPLATES).format(topic=topic)
    viral_score = random.randint(45, 85)
    score_reasons = {
        range(45, 60): "Moderate engagement potential. Consider adding stronger hooks.",
        range(60, 75): "Good potential. Strong visual appeal and relatable content.",
        range(75, 86): "High viral potential! Strong hook, emotional appeal, and shareability.",
    }
    reason = "Decent content with room for optimization."
    for r, msg in score_reasons.items():
        if viral_score in r:
            reason = msg
            break

    short = f"{clean_text[:80].strip()} What do you think?"
    long = (
        f"There's something special about {clean_text[:100].strip()} "
        f"It reminds us why we create content in the first place. "
        f"Every moment like this is worth sharing with the world. "
        f"Let this be your sign to embrace the beauty around you."
    )
    funny = random.choice([
        f"Plot twist: {clean_text[:80].strip()} I know, right?! Mind = blown!",
        f"Breaking news: {clean_text[:80].strip()} You're welcome for this info!",
        f"PSA: {clean_text[:80].strip()} Science has spoken (kind of).",
    ])
    professional = random.choice([
        f"Delivering value through thoughtfully composed content designed to resonate with the target audience.",
        f"A well-crafted piece that demonstrates quality content creation and strategic social media positioning.",
    ])
    travel = random.choice([
        f"Adventure awaits! {clean_text[:80].strip()} Wanderlust mode: activated.",
        f"Explore. Discover. Share. {clean_text[:80].strip()} Travel changes everything.",
        f"Wander often, wonder always. {clean_text[:80].strip()}",
    ])
    business = random.choice([
        f"Growth starts here. {clean_text[:80].strip()} Build your brand, one post at a time.",
        f"Entrepreneurship is about creating value. {clean_text[:80].strip()} Let's build together.",
    ])
    food = random.choice([
        f"Life is short, eat the cake. {clean_text[:80].strip()} Food is love made visible.",
        f"Food is the ingredient that binds us all. {clean_text[:80].strip()} Delicious moments.",
    ])
    luxury = random.choice([
        f"Indulge in the exquisite. {clean_text[:80].strip()} Elevate your experience.",
        f"Unparalleled sophistication awaits. {clean_text[:80].strip()} Because you deserve the best.",
    ])

    return {
        "caption": f"{clean_text[:100].strip()} What do you think?",
        "long_caption": long,
        "short_caption": short,
        "funny_caption": funny,
        "professional_caption": professional,
        "travel_caption": travel,
        "business_caption": business,
        "food_caption": food,
        "luxury_caption": luxury,
        "carousel_text": f"Slide 1: {hook}|||Slide 2: {clean_text[:80].strip()}|||Slide 3: Key takeaway: This content is worth your time.|||Slide 4: Why it matters for you.|||Slide 5: Save this for later!",
        "thumbnail_text": f"{topic.title()} You Need This",
        "alt_text": f"Visual content showing {clean_text[:120].strip()}",
        "hashtags": " ".join(selected_hashtags[:6]),
        "keywords": ", ".join(keywords[:5]),
        "emojis": " ".join(random.sample(["✨", "🔥", "💯", "🎯", "🚀", "💡", "⭐", "🌟", "💪", "🙌"], 4)),
        "cta": random.choice(CTA_OPTIONS),
        "hook": hook,
        "reel_title": f"{topic.title()} - You Need to See This!",
        "seo_tags": ", ".join(keywords[:5] + ["content", "social"]),
        "summary": f"Engaging content about {topic}. Optimized for social media reach and engagement.",
        "viral_score": viral_score,
        "viral_score_reason": reason,
    }


def _fallback_generate_text(prompt: str) -> str:
    lower = prompt.lower()
    if "rewrite" in lower:
        tone_match = re.search(r"'(\w+)' tone", prompt)
        if not tone_match:
            tone_match = re.search(r"tone:\s*'([^']+)'", prompt)
        tone = tone_match.group(1) if tone_match else "casual"
        length_match = re.search(r"LENGTH:\s*(short|medium|long|very long)", prompt, re.IGNORECASE)
        if not length_match:
            length_match = re.search(r"'(\w[\w\s]*?)' length", prompt)
        if not length_match:
            length_match = re.search(r"length:\s*'([^']+)'", prompt)
        length = length_match.group(1).strip().lower() if length_match else "medium"
        lines = prompt.split("\n")
        original = lines[-1].strip() if lines else prompt
        words = original.split()
        tone_rewrites = {
            "professional": [
                f"This content presents a compelling narrative with strong potential for audience engagement and meaningful impact.",
                f"A well-crafted piece that demonstrates quality content creation and strategic social media positioning.",
                f"Delivering value through thoughtfully composed content designed to resonate with the target audience.",
                f"Professional-grade content that balances authenticity with strategic messaging for maximum reach.",
            ],
            "casual": [
                f"Hey, check this out! {original.lower().rstrip('.')}. Pretty cool right?",
                f"So get this - {original.lower().rstrip('.')}. What do you think?",
                f"Just sharing something awesome: {original.lower().rstrip('.')}. Love it!",
                f"Real talk: {original.lower().rstrip('.')}. Definitely worth your time!",
            ],
            "funny": [
                f"Plot twist: {original.lower().rstrip('.')}. I know, right?! Mind = blown!",
                f"Breaking news: {original.lower().rstrip('.')}. You're welcome for this info!",
                f"Alert alert! {original.lower().rstrip('.')}. Yes, I'm fun at parties.",
                f"PSA: {original.lower().rstrip('.')}. Science has spoken (kind of).",
            ],
            "inspirational": [
                f"Never stop believing that {original.lower().rstrip('.')}. Your journey matters!",
                f"Every great story starts with {original.lower().rstrip('.')}. Dream big today!",
                f"The world is full of possibilities: {original.lower().rstrip('.')}. Embrace every moment!",
                f"Let this be your reminder that {original.lower().rstrip('.')}. You are capable of amazing things!",
            ],
            "urgent": [
                f"ATTENTION: {original} Time is running out - act NOW before it's too late!",
                f"ALERT: {original} Don't miss this opportunity - take action TODAY!",
                f"URGENT: {original} This won't last long - secure your spot immediately!",
                f"IMPORTANT: {original} Act fast - this is your moment!",
            ],
            "luxury": [
                f"Indulge in the exquisite: {original.rstrip('.')}. Elevate your experience to the next level.",
                f"Experience refined elegance: {original.rstrip('.')}. For those who appreciate the finest things.",
                f"Unparalleled sophistication awaits: {original.rstrip('.')}. Where luxury meets lifestyle.",
                f"Crafted for the discerning: {original.rstrip('.')}. Because you deserve nothing but the best.",
            ],
            "minimalist": [
                f"{original.rstrip('.')}. Simple. Beautiful. Essential.",
                f"Less is more. {original.rstrip('.')}. That's it.",
                f"{original.rstrip('.')}. Nothing more needed.",
                f"The essence: {original.rstrip('.')}. Pure and simple.",
            ],
            "storytelling": [
                f"It all started with a vision: {original.lower().rstrip('.')}. And that changed everything.",
                f"Imagine a world where {original.lower().rstrip('.')}. That's the story we're living.",
                f"Here's how it happened: {original.lower().rstrip('.')}. A journey worth sharing.",
                f"Picture a moment where {original.lower().rstrip('.')}. That moment is now.",
            ],
        }
        options = tone_rewrites.get(tone, tone_rewrites.get("casual"))
        base_result = random.choice(options)

        target_lengths = {"short": 15, "medium": 30, "long": 60, "very long": 100}
        target_words = target_lengths.get(length, 30)
        current_words = len(base_result.split())

        if current_words > target_words:
            result = " ".join(base_result.split()[:target_words]).rstrip('.!?')
            result += "."
        elif current_words < target_words - 10 and length in ("long", "very long"):
            extras = [
                f" This is worth sharing with others who appreciate great content.",
                f" Take a moment to appreciate the beauty in everyday experiences.",
                f" Great content like this deserves to be seen by everyone.",
                f" Don't forget to save this for when you need inspiration.",
                f" Share this with your friends and spread the word.",
                f" The best things in life are meant to be experienced and shared.",
                f" Stay tuned for more amazing content like this coming your way.",
                f" Make sure to follow for daily inspiration and updates.",
            ]
            extra_words_needed = target_words - current_words
            extra_text = ""
            while len(extra_text.split()) < extra_words_needed and extras:
                extra_text += " " + extras.pop(random.randint(0, len(extras) - 1))
            result = base_result.rstrip('.!?') + "." + extra_text
        else:
            result = base_result

        return result
    if "translate" in lower:
        lang_match = re.search(r"to\s+(\w[\w\s]{0,30})\.", prompt)
        lang = lang_match.group(1).strip() if lang_match else "the target language"
        sep = prompt.find("\n\n")
        original = prompt[sep + 2:].strip() if sep != -1 else prompt
        lang_key = lang.lower().strip()

        label_translations = {
            "gujarati": {"Caption:": "કેપ્શન:", "Summary:": "સારાંશ:"},
            "hindi": {"Caption:": "कैप्शन:", "Summary:": "सारांश:"},
            "marathi": {"Caption:": "कॅप्शन:", "Summary:": "सारांશ:"},
            "tamil": {"Caption:": "தலைப்பு:", "Summary:": "சுருக்கம்:"},
            "sanskrit": {"Caption:": "शीर्षकम्:", "Summary:": "सारांशः:"},
        }

        word_dict = {
            "gujarati": {
                "i": "હું", "am": "છું", "is": "છે", "are": "છે", "was": "હતો", "were": "હતા",
                "the": "", "a": "એક", "an": "એક", "this": "આ", "that": "તે", "it": "તે",
                "you": "તમે", "your": "તમારું", "we": "અમે", "they": "તેઓ", "he": "તે", "she": "તે",
                "my": "મારું", "our": "અમારું", "their": "તેમનું", "his": "તેનું", "her": "તેનું",
                "and": "અને", "or": "અથવા", "but": "પરંતુ", "with": "સાથે", "without": "વગર",
                "in": "માં", "on": "પર", "at": "પર", "to": "ને", "for": "માટે", "from": "થી",
                "of": "નું", "about": "વિશે", "into": "માં", "through": "દ્વારા",
                "not": "નહીં", "no": "ના", "yes": "હા", "never": "ક્યારેય", "always": "હંમેશા",
                "can": "શકો", "could": "શકો", "will": "કરશે", "would": "કરશે", "should": "જોઈએ",
                "must": "જરૂર", "may": "શકે", "might": "શકે",
                "do": "કરો", "does": "કરે", "did": "કર્યું", "have": "ધરાવો", "has": "ધરાવે",
                "had": "ધરાવ્યું", "get": "મેળવો", "got": "મેળવ્યું",
                "go": "જાઓ", "come": "આવો", "see": "જુઓ", "look": "જુઓ", "watch": "જુઓ",
                "make": "બનાવો", "take": "લો", "give": "આપો", "tell": "કહો", "say": "કહો",
                "think": "વિચારો", "know": "જાણો", "want": "ઈચ્છો", "need": "જરૂર",
                "like": "ગમે", "love": "પ્રેમ", "enjoy": "માણો", "happy": "ખુશ",
                "good": "સારું", "great": "મહાન", "best": "શ્રેષ્ઠ", "beautiful": "સુંદર",
                "amazing": "અદ્ભુત", "wonderful": "અદ્ભુત", "incredible": "અવિશ્વસનીય",
                "perfect": "સંપૂર્ણ", "awesome": "અદ્ભુત", "fantastic": "શાનદાર",
                "world": "દુનિયા", "life": "જીવન", "day": "દિવસ", "time": "સમય",
                "place": "જગ્યા", "home": "ઘર", "heart": "હૃદય", "dream": "સપનું",
                "travel": "પ્રવાસ", "explore": "શોધો", "discover": "શોધો",
                "create": "બનાવો", "share": "શેર કરો", "post": "પોસ્ટ",
                "content": "સામગ્રી", "social": "સામાજિક", "media": "મીડિયા",
                "photo": "ફોટો", "picture": "ચિત્ર", "video": "વિડિયો",
                "today": "આજે", "now": "હવે", "here": "અહીં", "there": "ત્યાં",
                "very": "ખૂબ", "so": "એટલે", "just": "માત્ર", "also": "પણ",
                "more": "વધુ", "all": "બધા", "every": "દરેક", "new": "નવું",
                "start": "શરૂ કરો", "begin": "શરૂ કરો", "finish": "સમાપ્ત કરો",
                "stop": "બંધ કરો", "wait": "રાહ જુઓ", "try": "પ્રયાસ કરો",
                "feel": "અનુભવો", "experience": "અનુભવ", "memory": "યાદ",
                "moment": "ક્ષણ", "today": "આજે", "tomorrow": "કાલે",
                "morning": "સવારે", "evening": "સાંજે", "night": "રાતે",
                "nature": "પ્રકૃતિ", "mountain": "પર્વત", "beach": "દરિયા કિનારો",
                "city": "શહેર", "country": "દેશ", "people": "લોકો",
                "friend": "મિત્ર", "family": "પરિવાર", "children": "બાળકો",
                "eat": "ખાઓ", "drink": "પીઓ", "sleep": "સૂતા",
                "work": "કામ", "play": "રમો", "read": "વાંચો", "write": "લખો",
                "big": "મોટું", "small": "નાનું", "long": "લાંબું", "short": "ટૂંકું",
                "hot": "ગરમ", "cold": "ઠંડું", "fast": "ઝડપી", "slow": "ધીમું",
                "up": "ઉપર", "down": "નીચે", "left": "ડાબે", "right": "જમણે",
                "way": "રસ્તો", "road": "રસ્તો", "light": "પ્રકાશ", "dark": "અંધારું",
                "color": "રંગ", "red": "લાલ", "blue": "વાદળી", "green": "લીલું",
                "water": "પાણી", "fire": "આગ", "air": "હવા", "earth": "પૃથ્વી",
                "sun": "સૂર્ય", "moon": "ચંદ્ર", "star": "તારો", "sky": "આકાશ",
                "book": "પુસ્તક", "song": "ગીત", "music": "સંગીત",
                "true": "સાચું", "false": "ખોટું", "real": "સાચું", "fake": "નકલી",
                "help": "મદદ", "hope": "આશા", "faith": "વિશ્વાસ",
                "power": "શક્તિ", "strength": "તાકાત", "courage": "હિંમત",
                "success": "સફળતા", "failure": "નિષ્ફળતા",
                "question": "પ્રશ્ન", "answer": "જવાબ", "problem": "સમસ્યા",
                "solution": "ઉકેલ", "idea": "વિચાર", "plan": "યોજના",
                "change": "બદલાવ", "future": "ભવિષ્ય", "past": "ભૂતકાળ",
                "present": "વર્તમાન", "age": "ઉંમર", "year": "વર્ષ",
                "month": "મહિનો", "week": "અઠવાડિયું", "hour": "કલાક",
                "minute": "મિનિટ", "second": "સેકન્ડ",
                "happy": "ખુશ", "sad": "દુઃખી", "angry": "ગુસ્સે", "afraid": "ડરેલું",
                "excited": "ઉત્સાહિત", "proud": "ગર્વિત", "kind": "દયાળુ",
                "strong": "મજબૂત", "brave": "બહાદુર", "smart": "હોશિયાર",
                "easy": "સરળ", "hard": "મુશ્કેલ", "important": "મહત્વપૂર્ણ",
                "possible": "શક્ય", "impossible": "અશક્ય", "different": "અલગ",
                "same": "એક જેવું", "first": "પહેલું", "last": "છેલ્લું",
                "next": "આગળું", "back": "પાછળ", "keep": "રાખો",
                "let": "આપો", "put": "મૂકો", "run": "દોડો", "walk": "ચાલો",
                "talk": "વાત કરો", "listen": "સાંભળો", "open": "ખોલો",
                "close": "બંધ કરો", "show": "બતાવો", "use": "વાપરો",
                "find": "શોધો", "build": "બનાવો", "break": "તોડો",
                "follow": "અનુસરો", "lead": "આગેવાની", "move": "ચાલો",
                "stand": "ઉભા રહો", "sit": "બેસો", "fall": "પડો",
                "grow": "વધો", "learn": "શીખો", "teach": "શીખવો",
                "pay": "ચૂકવો", "buy": "ખરીદો", "sell": "વેચો",
                "send": "મોકલો", "receive": "મેળવો", "call": "ફોન કરો",
                "remember": "યાદ રાખો", "forget": "ભૂલી જાઓ",
                "believe": "વિશ્વાસ કરો", "understand": "સમજો",
                "care": "પરવાહ", "miss": "યાદ આવે", "trust": "વિશ્વાસ",
                "inspire": "પ્રેરણા આપો", "motivate": "પ્રેરિત કરો",
                "dream": "સપનું", "achieve": "પ્રાપ્ત કરો", "goal": "લક્ષ્ય",
                "passion": "જુસ્સો", "purpose": "હેતુ", "value": "મૂલ્ય",
                "energy": "ઊર્જા", "peace": "શાંતિ", "joy": "આનંદ",
                "love": "પ્રેમ", "beauty": "સુંદરતા", "truth": "સત્ય",
                "journey": "યાત્રા", "adventure": "સાહસ",
                "destination": "ગંતવ્ય", "destinations": "ગંતવ્યો",
                "memory": "યાદ", "memories": "યાદો",
                "unforgettable": "અભૂતપૂર્વ", "breathtaking": "અદ્ભુત",
                "corner": "ખૂણું", "passionate": "ઉત્સાહી",
                "traveler": "પ્રવાસી", "explorer": "શોધક",
                "adventurous": "સાહસિક", "discover": "શોધો",
                "discovery": "શોધ", "journeys": "યાત્રાઓ",
                "path": "પાથ", "road": "રસ્તો",
                "flight": "ફ્લાઈટ", "hotel": "હોટેલ",
                "restaurant": "રેસ્ટોરન્ટ", "food": "ખોરાક",
                "culture": "સંસ્કૃતિ", "tradition": "પરંપરા",
                "heritage": "વારસો", "history": "ઇતિહાસ",
                "architecture": "આર્કિટેક્ચર", "art": "કલા",
                "music": "સંગીત", "dance": "નૃત્ય",
                "festival": "ઉત્સવ", "celebration": "ઉજવણી",
                "sunrise": "સૂર્યોદય", "sunset": "સૂર્યાસ્ત",
                "ocean": "મહાસાગર", "sea": "દરિયો", "river": "નદી",
                "forest": "જંગલ", "desert": "રણ",
                "snow": "બરફ", "rain": "વરસાદ", "wind": "પવન",
                "spring": "વસંત", "summer": "ગ્રીષ્મ", "autumn": "પાનખર", "winter": "શિયાળો",
                "sun": "સૂર્ય", "moon": "ચંદ્ર", "star": "તારો", "sky": "આકાશ",
                "water": "પાણી", "fire": "આગ", "air": "હવા", "earth": "પૃથ્વી",
                "light": "પ્રકાશ", "dark": "અંધારું", "color": "રંગ",
                "mountain": "પર્વત", "beach": "દરિયા કિનારો",
                "city": "શહેર", "country": "દેશ", "people": "લોકો",
                "friend": "મિત્ર", "family": "પરિવાર", "children": "બાળકો",
                "morning": "સવાર", "afternoon": "બપોર", "evening": "સાંજ", "night": "રાત",
                "today": "આજે", "tomorrow": "કાલે",
                "modern": "આધુનિક", "ancient": "પ્રાચીન",
                "traditional": "પરંપરાગત", "famous": "પ્રસિદ્ધ", "popular": "લોકપ્રિય",
                "unique": "અનોખું", "special": "વિશેષ",
                "digital": "ડિજિટલ", "online": "ઓનલાઈન",
                "global": "વૈશ્વિક", "local": "સ્થાનિક",
                "safe": "સુરક્ષિત", "dangerous": "ખતરનાક",
                "healthy": "તંદુરસ્ત", "strong": "મજબૂત", "weak": "નબળું",
                "calm": "શાંત", "peaceful": "શાંતિપૂર્ણ",
                "clean": "સ્વચ્છ", "dry": "સૂકું", "wet": "ભીનું",
                "hot": "ગરમ", "warm": "ગરમ", "cool": "ઠંડું", "cold": "ઠંડું",
                "soft": "નરમ", "hard": "સખત",
                "sweet": "મીઠું", "sour": "ખાટું", "bitter": "કડવું",
                "bright": "તેજસ્વી", "rich": "ધનિક", "poor": "ગરીબ",
                "young": "યુવાન", "old": "જૂનું", "fresh": "તાજું",
                "full": "ભરેલું", "empty": "ખાલી",
                "open": "ખુલ્લું", "closed": "બંધ",
                "fast": "ઝડપી", "slow": "ધીમું",
                "early": "વહેલું", "late": "મોડું", "soon": "જલ્દી",
                "always": "હંમેશા", "never": "ક્યારેય નહીં",
                "sometimes": "ક્યારેક", "often": "ઘણીવાર",
                "daily": "દૈનિક", "weekly": "સાપ્તાહિક",
                "together": "સાથે", "apart": "અલગ",
                "above": "ઉપર", "below": "નીચે", "between": "વચ્ચે",
                "behind": "પાછળ", "before": "આગળ", "after": "પછી",
                "because": "કારણ કે", "although": "જો કે",
                "while": "જ્યારે", "since": "જ્યારથી",
                "if": "જો", "already": "પહેલેથી", "still": "હજુ",
                "true": "સાચું", "false": "ખોટું", "real": "વાસ્તવિક", "fake": "નકલી",
                "help": "મદદ", "hope": "આશા", "faith": "વિશ્વાસ",
                "power": "શક્તિ", "strength": "તાકાત", "courage": "હિંમત",
                "success": "સફળતા", "failure": "નિષ્ફળતા",
                "question": "પ્રશ્ન", "answer": "જવાબ", "problem": "સમસ્યા",
                "solution": "ઉકેલ", "idea": "વિચાર", "plan": "યોજના",
                "change": "બદલાવ", "future": "ભવિષ્ય", "past": "ભૂતકાળ",
                "age": "ઉંમર", "year": "વર્ષ", "month": "મહિનો",
                "week": "અઠવાડિયું", "hour": "કલાક",
                "happy": "ખુશ", "sad": "દુઃખી", "angry": "ગુસ્સે",
                "excited": "ઉત્સાહિત", "proud": "ગર્વિત", "kind": "દયાળુ",
                "brave": "બહાદુર", "smart": "હોશિયાર",
                "easy": "સરળ", "hard": "મુશ્કેલ", "important": "મહત્વપૂર્ણ",
                "possible": "શક્ય", "impossible": "અશક્ય", "different": "અલગ",
                "same": "એક જેવું", "first": "પહેલું", "last": "છેલ્લું",
                "next": "આગળું", "back": "પાછળ", "keep": "રાખો",
                "let": "આપો", "put": "મૂકો", "run": "દોડો", "walk": "ચાલો",
                "talk": "વાત કરો", "listen": "સાંભળો",
                "show": "બતાવો", "use": "વાપરો",
                "find": "શોધો", "build": "બનાવો",
                "follow": "અનુસરો", "lead": "આગેવાની", "move": "ચાલો",
                "stand": "ઉભા રહો", "sit": "બેસો", "fall": "પડો",
                "grow": "વધો", "learn": "શીખો", "teach": "શીખવો",
                "buy": "ખરીદો", "sell": "વેચો",
                "send": "મોકલો", "receive": "મેળવો",
                "remember": "યાદ રાખો", "forget": "ભૂલી જાઓ",
                "believe": "વિશ્વાસ કરો", "understand": "સમજો",
                "care": "પરવાહ", "miss": "યાદ આવે", "trust": "વિશ્વાસ",
                "inspire": "પ્રેરણા આપો", "motivate": "પ્રેરિત કરો",
                "achieve": "પ્રાપ્ત કરો", "goal": "લક્ષ્ય",
                "passion": "જુસ્સો", "purpose": "હેતુ", "value": "મૂલ્ય",
                "energy": "ઊર્જા", "peace": "શાંતિ", "joy": "આનંદ",
                "love": "પ્રેમ", "beauty": "સુંદરતા", "truth": "સત્ય",
                "book": "પુસ્તક", "song": "ગીત",
                "computer": "કમ્પ્યુટર", "phone": "ફોન",
                "camera": "કેમેરા", "video": "વિડિયો",
                "photo": "ફોટો", "picture": "ચિત્ર",
                "big": "મોટું", "small": "નાનું", "long": "લાંબું", "short": "ટૂંકું",
                "new": "નવું", "up": "ઉપર", "down": "નીચે",
                "dog": "કૂતરો", "cat": "બિલાડી",
                "tree": "વૃક્ષ", "flower": "ફૂલ",
            },
            "hindi": {
                "i": "मैं", "am": "हूँ", "is": "है", "are": "हैं", "was": "था",
                "the": "", "a": "एक", "this": "यह", "that": "वह", "it": "यह",
                "you": "आप", "your": "आपका", "we": "हम", "they": "वे",
                "my": "मेरा", "our": "हमारा", "their": "उनका",
                "and": "और", "or": "या", "but": "लेकिन", "with": "साथ", "without": "बिना",
                "in": "में", "on": "पर", "to": "को", "for": "के लिए", "from": "से",
                "of": "का", "about": "के बारे में",
                "not": "नहीं", "never": "कभी नहीं", "always": "हमेशा",
                "can": "सकता है", "will": "होगा", "should": "चाहिए", "must": "जरूर",
                "do": "करो", "does": "करता है", "have": "है", "has": "है",
                "good": "अच्छा", "great": "महान", "best": "सर्वोत्तम",
                "beautiful": "सुंदर", "amazing": "अद्भुत", "wonderful": "अद्भुत",
                "world": "दुनिया", "life": "जीवन", "day": "दिन", "time": "समय",
                "dream": "सपना", "travel": "यात्रा", "explore": "खोजो",
                "discover": "खोजो", "create": "बनाओ", "share": "साझा करो",
                "content": "सामग्री", "social": "सामाजिक", "media": "मीडिया",
                "today": "आज", "now": "अब", "here": "यहाँ", "there": "वहाँ",
                "very": "बहुत", "so": "इसलिए", "just": "बस", "also": "भी",
                "more": "अधिक", "all": "सभी", "every": "हर", "new": "नया",
                "people": "लोग", "friend": "दोस्त", "family": "परिवार",
                "happy": "खुश", "sad": "उदास", "love": "प्यार",
                "heart": "दिल", "home": "घर", "nature": "प्रकृति",
                "mountain": "पहाड़", "beach": "समुद्र तट", "city": "शहर",
                "country": "देश", "sun": "सूरज", "moon": "चाँद", "star": "तारा",
                "sky": "आसमान", "water": "पानी", "fire": "आग", "air": "हवा",
                "light": "प्रकाश", "dark": "अंधेरा", "color": "रंग",
                "big": "बड़ा", "small": "छोटा", "long": "लंबा", "short": "छोटा",
                "new": "नया", "old": "पुराना", "fast": "तेज़", "slow": "धीमा",
                "easy": "आसान", "hard": "कठिन", "important": "महत्वपूर्ण",
                "possible": "संभव", "impossible": "असंभव",
                "success": "सफलता", "failure": "असफलता",
                "strength": "ताकत", "courage": "हिम्मत", "power": "शक्ति",
                "hope": "उम्मीद", "faith": "विश्वास", "peace": "शांति",
                "joy": "खुशी", "energy": "ऊर्जा", "beauty": "सुंदरता",
                "truth": "सत्य", "journey": "यात्रा", "adventure": "साहस",
                "destination": "गंतव्य", "memory": "याद",
                "passionate": "जुनूनी", "corner": "कोना",
                "start": "शुरू करो", "stop": "रुको", "wait": "इंतज़ार करो",
                "think": "सोचो", "know": "जानो", "want": "चाहो", "need": "जरूरत",
                "like": "पसंद", "enjoy": "आनंद लो",
            },
            "marathi": {
                "i": "मी", "am": "आहे", "is": "आहे", "are": "आहेत",
                "the": "", "a": "एक", "this": "हे", "that": "ते", "it": "ते",
                "you": "तुम्ही", "your": "तुमचे", "we": "आम्ही", "they": "ते",
                "and": "आणि", "or": "किंवा", "but": "पण", "with": "सोबत",
                "in": "मध्ये", "on": "वर", "to": "ला", "for": "साठी", "from": "पासून",
                "of": "चा", "about": "बद्दल",
                "not": "नाही", "never": "कधीही", "always": "नेहमी",
                "good": "चांगले", "great": "मोठे", "beautiful": "सुंदर",
                "amazing": "अद्भुत", "world": "जग", "life": "जीवन",
                "dream": "स्वप्न", "travel": "प्रवास", "explore": "शोधा",
                "love": "प्रेम", "happy": "आनंदी", "home": "घर",
                "people": "लोक", "friend": "मित्र", "family": "कुटुंब",
                "today": "आज", "now": "आता", "here": "इथे", "there": "तिथे",
                "nature": "निसर्ग", "mountain": "डोंगर", "beach": "किनारा",
                "city": "शहर", "country": "देश", "sun": "सूर्य", "moon": "चंद्र",
                "sky": "आकाश", "water": "पाणी", "light": "प्रकाश",
                "big": "मोठे", "small": "लहान", "new": "नवीन",
                "start": "सुरू करा", "stop": "थांबा", "wait": "थांबा",
                "think": "विचार करा", "know": "माहीत आहे", "want": "हवे",
                "share": "शेअर करा", "create": "तयार करा",
                "passionate": "उत्साही", "corner": "कोपरा",
            },
            "tamil": {
                "i": "நான்", "am": "இருக்கிறேன்", "is": "இருக்கிறது", "are": "இருக்கின்றன",
                "the": "", "a": "ஒரு", "this": "இது", "that": "அது",
                "you": "நீங்கள்", "we": "நாங்கள்", "they": "அவர்கள்",
                "and": "மற்றும்", "or": "அல்லது", "but": "ஆனால்", "with": "உடன்",
                "in": "இல்", "on": "மீது", "to": "க்கு", "for": "க்காக",
                "good": "நல்ல", "great": "பெரிய", "beautiful": "அழகான",
                "amazing": "அற்புதமான", "world": "உலகம்", "life": "வாழ்க்கை",
                "dream": "கனவு", "travel": "பயணம்", "explore": "ஆராயுங்கள்",
                "love": "அன்பு", "happy": "மகிழ்ச்சி", "home": "வீடு",
                "people": "மக்கள்", "friend": "நண்பர்", "family": "குடும்பம்",
                "today": "இன்று", "now": "இப்போது", "here": "இங்கே",
                "nature": "இயற்கை", "sun": "சூரியன்", "moon": "நிலவு",
                "sky": "வானம்", "water": "தண்ணீர்", "light": "ஒளி",
                "big": "பெரிய", "small": "சிறிய", "new": "புதிய",
                "start": "தொடங்குங்கள்", "stop": "நிறுத்துங்கள்",
                "think": "யோசியுங்கள்", "know": "அறிவீர்கள்", "want": "விரும்புகிறீர்கள்",
                "share": "பகிருங்கள்", "create": "உருவாக்குங்கள்",
                "passionate": "ஆர்வமுள்ள", "corner": "மூலை",
            },
            "spanish": {
                "i": "yo", "am": "soy", "is": "es", "are": "son",
                "the": "el/la", "a": "un/una", "this": "esto", "that": "eso",
                "you": "tú", "we": "nosotros", "ellos": "ellos",
                "and": "y", "or": "o", "but": "pero", "with": "con",
                "in": "en", "on": "sobre", "to": "a", "for": "para", "from": "de",
                "of": "de", "about": "sobre",
                "not": "no", "never": "nunca", "always": "siempre",
                "good": "bueno", "great": "genial", "beautiful": "hermoso",
                "amazing": "increíble", "world": "mundo", "life": "vida",
                "dream": "sueño", "travel": "viajar", "explore": "explorar",
                "love": "amor", "happy": "feliz", "home": "hogar",
                "people": "gente", "friend": "amigo", "family": "familia",
                "today": "hoy", "now": "ahora", "here": "aquí",
                "nature": "naturaleza", "sun": "sol", "moon": "luna",
                "sky": "cielo", "water": "agua", "light": "luz",
                "big": "grande", "small": "pequeño", "new": "nuevo",
                "start": "comenzar", "stop": "parar", "wait": "esperar",
                "think": "pensar", "know": "saber", "want": "querer",
                "share": "compartir", "create": "crear",
                "passionate": "apasionado", "corner": "esquina",
            },
            "french": {
                "i": "je", "am": "suis", "is": "est", "are": "sont",
                "the": "le/la", "a": "un/une", "this": "ceci", "that": "cela",
                "you": "vous", "we": "nous", "they": "ils",
                "and": "et", "or": "ou", "but": "mais", "with": "avec",
                "in": "dans", "on": "sur", "to": "à", "for": "pour", "from": "de",
                "not": "ne pas", "never": "jamais", "always": "toujours",
                "good": "bon", "great": "génial", "beautiful": "beau",
                "amazing": "incroyable", "world": "monde", "life": "vie",
                "dream": "rêve", "travel": "voyager", "explore": "explorer",
                "love": "amour", "happy": "heureux", "home": "maison",
                "people": "gens", "friend": "ami", "family": "famille",
                "today": "aujourd'hui", "now": "maintenant", "here": "ici",
                "nature": "nature", "sun": "soleil", "moon": "lune",
                "sky": "ciel", "water": "eau", "light": "lumière",
                "big": "grand", "small": "petit", "new": "nouveau",
                "start": "commencer", "stop": "arrêter", "wait": "attendre",
                "think": "penser", "know": "savoir", "want": "vouloir",
                "share": "partager", "create": "créer",
                "passionate": "passionné", "corner": "coin",
            },
            "german": {
                "i": "ich", "am": "bin", "is": "ist", "are": "sind",
                "the": "der/die/das", "a": "ein/eine", "this": "dies", "that": "das",
                "you": "du", "we": "wir", "they": "sie",
                "and": "und", "or": "oder", "but": "aber", "with": "mit",
                "in": "in", "on": "auf", "to": "zu", "for": "für", "from": "von",
                "not": "nicht", "never": "nie", "always": "immer",
                "good": "gut", "great": "groß", "beautiful": "schön",
                "amazing": "erstaunlich", "world": "Welt", "life": "Leben",
                "dream": "Traum", "travel": "Reise", "explore": "erkunden",
                "love": "Liebe", "happy": "glücklich", "home": "Zuhause",
                "people": "Leute", "friend": "Freund", "family": "Familie",
                "today": "heute", "now": "jetzt", "here": "hier",
                "nature": "Natur", "sun": "Sonne", "moon": "Mond",
                "sky": "Himmel", "water": "Wasser", "light": "Licht",
                "big": "groß", "small": "klein", "new": "neu",
                "start": "anfangen", "stop": "stoppen", "wait": "warten",
                "think": "denken", "know": "wissen", "want": "wollen",
                "share": "teilen", "create": "erstellen",
                "passionate": "leidenschaftlich", "corner": "Ecke",
            },
            "japanese": {
                "i": "私は", "am": "です", "is": "です", "are": "です",
                "the": "", "a": "一つの", "this": "これ", "that": "それ",
                "you": "あなた", "we": "私たち", "they": "彼ら",
                "and": "と", "or": "または", "but": "しかし", "with": "と一緒",
                "in": "の中で", "on": "の上に", "to": "に", "for": "のために",
                "not": "ない", "never": "決して", "always": "いつも",
                "good": "良い", "great": "素晴らしい", "beautiful": "美しい",
                "amazing": "素晴らしい", "world": "世界", "life": "人生",
                "dream": "夢", "travel": "旅行", "explore": "探検",
                "love": "愛", "happy": "幸せ", "home": "家",
                "people": "人々", "friend": "友達", "family": "家族",
                "today": "今日", "now": "今", "here": "ここ",
                "nature": "自然", "sun": "太陽", "moon": "月",
                "sky": "空", "water": "水", "light": "光",
                "big": "大きい", "small": "小さい", "new": "新しい",
                "start": "始める", "stop": "止める", "wait": "待つ",
                "think": "考える", "know": "知る", "want": "欲しい",
                "share": "共有する", "create": "作る",
                "passionate": "情熱的な", "corner": "角",
            },
            "chinese (simplified)": {
                "i": "我", "am": "是", "is": "是", "are": "是",
                "the": "", "a": "一个", "this": "这", "that": "那",
                "you": "你", "we": "我们", "they": "他们",
                "and": "和", "or": "或", "but": "但是", "with": "与",
                "in": "在", "on": "在", "to": "到", "for": "为了",
                "not": "不", "never": "从不", "always": "总是",
                "good": "好", "great": "伟大", "beautiful": "美丽",
                "amazing": "惊人", "world": "世界", "life": "生活",
                "dream": "梦想", "travel": "旅行", "explore": "探索",
                "love": "爱", "happy": "快乐", "home": "家",
                "people": "人们", "friend": "朋友", "family": "家庭",
                "today": "今天", "now": "现在", "here": "这里",
                "nature": "自然", "sun": "太阳", "moon": "月亮",
                "sky": "天空", "water": "水", "light": "光",
                "big": "大", "small": "小", "new": "新",
                "start": "开始", "stop": "停止", "wait": "等待",
                "think": "想", "know": "知道", "want": "想要",
                "share": "分享", "create": "创造",
                "passionate": "热情的", "corner": "角落",
            },
            "korean": {
                "i": "나는", "am": "이다", "is": "이다", "are": "이다",
                "the": "", "a": "하나의", "this": "이것", "that": "그것",
                "you": "당신", "we": "우리", "they": "그들",
                "and": "그리고", "or": "또는", "but": "하지만", "with": "와 함께",
                "in": "안에", "on": "위에", "to": "에", "for": "을 위해",
                "not": "아니다", "never": "절대", "always": "항상",
                "good": "좋은", "great": "위대한", "beautiful": "아름다운",
                "amazing": "놀라운", "world": "세계", "life": "인생",
                "dream": "꿈", "travel": "여행", "explore": "탐험",
                "love": "사랑", "happy": "행복한", "home": "집",
                "people": "사람들", "friend": "친구", "family": "가족",
                "today": "오늘", "now": "지금", "here": "여기",
                "nature": "자연", "sun": "태양", "moon": "달",
                "sky": "하늘", "water": "물", "light": "빛",
                "big": "큰", "small": "작은", "new": "새로운",
                "start": "시작하다", "stop": "멈추다", "wait": "기다리다",
                "think": "생각하다", "know": "알다", "want": "원하다",
                "share": "공유하다", "create": "만들다",
                "passionate": "열정적인", "corner": "구석",
            },
            "arabic": {
                "i": "أنا", "am": "أكون", "is": "هو", "are": "هم",
                "the": "ال", "a": "واحد", "this": "هذا", "that": "ذلك",
                "you": "أنت", "we": "نحن", "they": "هم",
                "and": "و", "or": "أو", "but": "لكن", "with": "مع",
                "in": "في", "on": "على", "to": "إلى", "for": "ل",
                "not": "لا", "never": "أبداً", "always": "دائماً",
                "good": "جيد", "great": "عظيم", "beautiful": "جميل",
                "amazing": "مذهل", "world": "عالم", "life": "حياة",
                "dream": "حلم", "travel": "سفر", "explore": "استكشف",
                "love": "حب", "happy": "سعيد", "home": "منزل",
                "people": "ناس", "friend": "صديق", "family": "عائلة",
                "today": "اليوم", "now": "الآن", "here": "هنا",
                "nature": "طبيعة", "sun": "شمس", "moon": "قمر",
                "sky": "سماء", "water": "ماء", "light": "ضوء",
                "big": "كبير", "small": "صغير", "new": "جديد",
                "start": "ابدأ", "stop": "توقف", "wait": "انتظر",
                "think": "فكر", "know": "اعرف", "want": "أريد",
                "share": "شارك", "create": "أنشئ",
                "passionate": "متحمس", "corner": "زاوية",
            },
            "russian": {
                "i": "я", "am": "являюсь", "is": "является", "are": "являются",
                "the": "", "a": "один", "this": "это", "that": "то",
                "you": "ты", "we": "мы", "they": "они",
                "and": "и", "or": "или", "but": "но", "with": "с",
                "in": "в", "on": "на", "to": "к", "for": "для", "from": "от",
                "not": "не", "never": "никогда", "always": "всегда",
                "good": "хороший", "great": "великий", "beautiful": "красивый",
                "amazing": "удивительный", "world": "мир", "life": "жизнь",
                "dream": "мечта", "travel": "путешествие", "explore": "исследовать",
                "love": "любовь", "happy": "счастливый", "home": "дом",
                "people": "люди", "friend": "друг", "family": "семья",
                "today": "сегодня", "now": "сейчас", "here": "здесь",
                "nature": "природа", "sun": "солнце", "moon": "луна",
                "sky": "небо", "water": "вода", "light": "свет",
                "big": "большой", "small": "маленький", "new": "новый",
                "start": "начать", "stop": "остановиться", "wait": "ждать",
                "think": "думать", "know": "знать", "want": "хотеть",
                "share": "делиться", "create": "создавать",
                "passionate": "страстный", "corner": "угол",
            },
            "portuguese": {
                "i": "eu", "am": "sou", "is": "é", "are": "são",
                "the": "o/a", "a": "um/uma", "this": "isto", "that": "isso",
                "you": "você", "we": "nós", "they": "eles",
                "and": "e", "or": "ou", "but": "mas", "with": "com",
                "in": "em", "on": "sobre", "to": "para", "for": "para",
                "not": "não", "never": "nunca", "always": "sempre",
                "good": "bom", "great": "ótimo", "beautiful": "bonito",
                "amazing": "incrível", "world": "mundo", "life": "vida",
                "dream": "sonho", "travel": "viajar", "explore": "explorar",
                "love": "amor", "happy": "feliz", "home": "lar",
                "people": "pessoas", "friend": "amigo", "family": "família",
                "today": "hoje", "now": "agora", "here": "aqui",
                "nature": "natureza", "sun": "sol", "moon": "lua",
                "sky": "céu", "water": "água", "light": "luz",
                "big": "grande", "small": "pequeno", "new": "novo",
                "start": "começar", "stop": "parar", "wait": "esperar",
                "think": "pensar", "know": "saber", "want": "querer",
                "share": "compartilhar", "create": "criar",
                "passionate": "apaixonado", "corner": "canto",
            },
            "italian": {
                "i": "io", "am": "sono", "is": "è", "are": "sono",
                "the": "il/la", "a": "un/una", "this": "questo", "that": "quello",
                "you": "tu", "we": "noi", "they": "loro",
                "and": "e", "or": "o", "but": "ma", "with": "con",
                "in": "in", "on": "su", "to": "a", "for": "per",
                "not": "non", "never": "mai", "always": "sempre",
                "good": "buono", "great": "grande", "beautiful": "bello",
                "amazing": "incredibile", "world": "mondo", "life": "vita",
                "dream": "sogno", "travel": "viaggio", "explore": "esplorare",
                "love": "amore", "happy": "felice", "home": "casa",
                "people": "persone", "friend": "amico", "family": "famiglia",
                "today": "oggi", "now": "adesso", "here": "qui",
                "nature": "natura", "sun": "sole", "moon": "luna",
                "sky": "cielo", "water": "acqua", "light": "luce",
                "big": "grande", "small": "piccolo", "new": "nuovo",
                "start": "iniziare", "stop": "fermare", "wait": "aspettare",
                "think": "pensare", "know": "sapere", "want": "volere",
                "share": "condividere", "create": "creare",
                "passionate": "appassionato", "corner": "angolo",
            },
            "dutch": {
                "i": "ik", "am": "ben", "is": "is", "are": "zijn",
                "the": "de/het", "a": "een", "this": "dit", "that": "dat",
                "you": "jij", "we": "wij", "they": "zij",
                "and": "en", "or": "of", "but": "maar", "with": "met",
                "in": "in", "on": "op", "to": "naar", "for": "voor",
                "not": "niet", "never": "nooit", "always": "altijd",
                "good": "goed", "great": "geweldig", "beautiful": "mooi",
                "amazing": "verbazingwekkend", "world": "wereld", "life": "leven",
                "dream": "droom", "travel": "reis", "explore": "verkennen",
                "love": "liefde", "happy": "blij", "home": "thuis",
                "people": "mensen", "friend": "vriend", "family": "familie",
                "today": "vandaag", "now": "nu", "here": "hier",
                "nature": "natuur", "sun": "zon", "moon": "maan",
                "sky": "lucht", "water": "water", "light": "licht",
                "big": "groot", "small": "klein", "new": "nieuw",
                "start": "beginnen", "stop": "stoppen", "wait": "wachten",
                "think": "denken", "know": "weten", "want": "willen",
                "share": "delen", "create": "maken",
                "passionate": "passioneel", "corner": "hoek",
            },
            "turkish": {
                "i": "ben", "am": "im", "is": "dir", "are": "dir",
                "the": "", "a": "bir", "this": "bu", "that": "şu",
                "you": "sen", "we": "biz", "they": "onlar",
                "and": "ve", "or": "veya", "but": "ama", "with": "ile",
                "in": "içinde", "on": "üzerinde", "to": "ya", "for": "için",
                "not": "değil", "never": "asla", "always": "her zaman",
                "good": "iyi", "great": "harika", "beautiful": "güzel",
                "amazing": "inanılmaz", "world": "dünya", "life": "hayat",
                "dream": "rüya", "travel": "seyahat", "explore": "keşfet",
                "love": "aşk", "happy": "mutlu", "home": "ev",
                "people": "insanlar", "friend": "arkadaş", "family": "aile",
                "today": "bugün", "now": "şimdi", "here": "burada",
                "nature": "doğa", "sun": "güneş", "moon": "ay",
                "sky": "gökyüzü", "water": "su", "light": "ışık",
                "big": "büyük", "small": "küçük", "new": "yeni",
                "start": "başla", "stop": "durdur", "wait": "bekle",
                "think": "düşün", "know": "bil", "want": "istiyorum",
                "share": "paylaş", "create": "oluştur",
                "passionate": "tutkulu", "corner": "köşe",
            },
            "thai": {
                "i": "ฉัน", "am": "เป็น", "is": "เป็น", "are": "เป็น",
                "the": "", "a": "หนึ่ง", "this": "นี้", "that": "นั้น",
                "you": "คุณ", "we": "เรา", "they": "พวกเขา",
                "and": "และ", "or": "หรือ", "but": "แต่", "with": "กับ",
                "in": "ใน", "on": "บน", "to": "ไปยัง", "for": "สำหรับ",
                "not": "ไม่", "never": "ไม่เคย", "always": "เสมอ",
                "good": "ดี", "great": "ยิ่งใหญ่", "beautiful": "สวยงาม",
                "amazing": "น่าทึ่ง", "world": "โลก", "life": "ชีวิต",
                "dream": "ความฝัน", "travel": "การเดินทาง", "explore": "สำรวจ",
                "love": "ความรัก", "happy": "มีความสุข", "home": "บ้าน",
                "people": "ผู้คน", "friend": "เพื่อน", "family": "ครอบครัว",
                "today": "วันนี้", "now": "ตอนนี้", "here": "ที่นี่",
                "nature": "ธรรมชาติ", "sun": "ดวงอาทิตย์", "moon": "ดวงจันทร์",
                "sky": "ท้องฟ้า", "water": "น้ำ", "light": "แสง",
                "big": "ใหญ่", "small": "เล็ก", "new": "ใหม่",
                "start": "เริ่ม", "stop": "หยุด", "wait": "รอ",
                "think": "คิด", "know": "รู้", "want": "ต้องการ",
                "share": "แชร์", "create": "สร้าง",
                "passionate": "หลงใหล", "corner": "มุม",
            },
            "vietnamese": {
                "i": "tôi", "am": "là", "is": "là", "are": "là",
                "the": "", "a": "một", "this": "này", "that": "đó",
                "you": "bạn", "we": "chúng tôi", "they": "họ",
                "and": "và", "or": "hoặc", "but": "nhưng", "with": "với",
                "in": "trong", "on": "trên", "to": "đến", "for": "cho",
                "not": "không", "never": "không bao giờ", "always": "luôn",
                "good": "tốt", "great": "tuyệt vời", "beautiful": "đẹp",
                "amazing": "tuyệt vời", "world": "thế giới", "life": "cuộc sống",
                "dream": "giấc mơ", "travel": "du lịch", "explore": "khám phá",
                "love": "tình yêu", "happy": "vui", "home": "nhà",
                "people": "mọi người", "friend": "bạn", "family": "gia đình",
                "today": "hôm nay", "now": "bây giờ", "here": "ở đây",
                "nature": "thiên nhiên", "sun": "mặt trời", "moon": "mặt trăng",
                "sky": "bầu trời", "water": "nước", "light": "ánh sáng",
                "big": "lớn", "small": "nhỏ", "new": "mới",
                "start": "bắt đầu", "stop": "dừng", "wait": "đợi",
                "think": "nghĩ", "know": "biết", "want": "muốn",
                "share": "chia sẻ", "create": "tạo",
                "passionate": "đam mê", "corner": "góc",
            },
        }

        def _translate_words(text: str, dictionary: dict) -> str:
            words = re.split(r'(\s+)', text)
            translated = []
            for word in words:
                if word.strip() == '':
                    translated.append(word)
                    continue
                lower_w = word.lower().strip(string.punctuation)
                punct_before = ""
                punct_after = ""
                if word and not word[0].isalpha():
                    punct_before = word[0]
                if word and not word[-1].isalpha():
                    punct_after = word[-1]
                if lower_w in dictionary and dictionary[lower_w]:
                    tr = dictionary[lower_w]
                    translated.append(punct_before + tr + punct_after)
                elif lower_w in dictionary and dictionary[lower_w] == "":
                    translated.append(punct_before + punct_after)
                else:
                    translated.append(word)
            return "".join(translated)

        translated = original
        if lang_key in label_translations:
            for eng, native in label_translations[lang_key].items():
                translated = translated.replace(eng, native)
        if lang_key in word_dict:
            translated = _translate_words(translated, word_dict[lang_key])
        return translated
    if "rate the viral potential" in lower or "viral score" in lower:
        score = random.randint(45, 85)
        reasons = [
            "Strong hook and emotional appeal drive engagement.",
            "High shareability factor with trending elements.",
            "Good visual appeal and relatable content.",
            "Moderate engagement potential. Consider adding stronger hooks.",
            "Viral potential boosted by relatable topic and trending format.",
        ]
        return f"{score}\n{random.choice(reasons)}"
    if "regenerate" in lower or "generate only" in lower:
        field_match = re.search(r"'(\w+)'", prompt)
        field = field_match.group(1) if field_match else "content"
        context_start = prompt.find("Current caption:")
        context_section = prompt[context_start:] if context_start != -1 else prompt
        topic_words = re.findall(r'\b[a-zA-Z]{4,}\b', context_section.lower())
        topic = topic_words[0] if topic_words else "this"
        field_templates = {
            "caption": [
                f"Discover something amazing about {topic} today!",
                f"This is what {topic} is all about. What's your take?",
                f"Unforgettable moments with {topic} - must see!",
                f"Your daily dose of {topic} inspiration!",
            ],
            "hashtags": ["#contentcreator #viral #trending #explorepage #instagood #fyp",
                         "#socialmediatips #digitalmarketing #growthhacking #engagement #reels",
                         "#photooftheday #content #marketing #viralcontent #trending"],
            "emojis": ["🔥 💯 🚀 ✨", "⭐ 💪 🎯 🙌", "💡 🌟 ✨ 🎉", "🚀 💥 🔥 💫"],
            "cta": ["Double tap if you agree!", "Drop a comment below!", "Share with someone who needs this!",
                    "Tag a friend!", "Save this for later!", "Follow for more content like this!"],
            "hook": [f"Wait for it... {topic} is about to change!",
                     f"Stop scrolling - {topic} is here!",
                     f"The truth about {topic} nobody tells you!",
                     f"3 things about {topic} that will blow your mind!"],
            "summary": [f"Compelling content about {topic} optimized for social media engagement.",
                        f"An engaging piece exploring {topic} for maximum audience reach."],
            "seo_tags": [f"{topic}, social media, content, engagement, viral, trending, marketing, growth"],
            "reel_title": [f"{topic.title()} That Will Blow Your Mind!",
                           f"Why {topic.title()} Changes Everything!",
                           f"Don't Miss This {topic.title()} Hack!"],
            "keywords": [f"{topic}, social media, content, engagement, viral, marketing, creative, trending"],
            "viral_score_reason": ["Strong hook and emotional appeal drive engagement.",
                                   "High shareability factor with trending elements.",
                                   "Good visual appeal and relatable content."],
        }
        options = field_templates.get(field, [f"Updated {field} for social media content."])
        return random.choice(options)
    context_start = prompt.find(":\n\n")
    context = prompt[context_start + 3:].strip() if context_start != -1 else prompt
    keywords = _extract_keywords_from_text(context)
    topic = keywords[0] if keywords else "content"
    return f"Optimized {topic} content for social media engagement and reach."


MYMEMORY_LANG_CODES = {
    "gujarati": "gu", "hindi": "hi", "marathi": "mr", "tamil": "ta",
    "sanskrit": "sa", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt-br", "dutch": "nl", "turkish": "tr",
    "thai": "th", "vietnamese": "vi", "japanese": "ja",
    "chinese (simplified)": "zh-cn", "arabic": "ar", "russian": "ru",
    "korean": "ko", "english": "en",
}


async def _mymemory_translate(text: str, target_language: str) -> str:
    lang_key = target_language.lower().strip()
    lang_code = MYMEMORY_LANG_CODES.get(lang_key)
    if not lang_code:
        for known, code in MYMEMORY_LANG_CODES.items():
            if known in lang_key or lang_key in known:
                lang_code = code
                break
    if not lang_code:
        logger.warning("Unknown language for MyMemory: %s", target_language)
        return text

    lines = text.split("\n")
    translated_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            translated_lines.append("")
            continue
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": line, "langpair": f"en|{lang_code}"},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("responseStatus") == 200:
                    translated = data["responseData"]["translatedText"]
                    if translated and translated.strip():
                        translated_lines.append(translated)
                        continue
        except Exception as e:
            logger.warning("MyMemory API failed for line: %s", e)
        translated_lines.append(line)
    return "\n".join(translated_lines)


class AIProvider:
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self._ollama_available = None

    async def _check_ollama(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                self._ollama_available = True
                return True
        except Exception:
            self._ollama_available = False
            logger.warning("Ollama not available. Using fallback content generator.")
            return False

    async def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> dict:
        if not await self._check_ollama():
            logger.info("Using fallback content generator")
            return _fallback_generate_content(prompt)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["message"]["content"].strip()
                return json.loads(content)
        except httpx.ConnectError:
            self._ollama_available = False
            logger.warning("Ollama disconnected. Using fallback content generator.")
            return _fallback_generate_content(prompt)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama HTTP error {e.response.status_code}: {e.response.text}")
        except json.JSONDecodeError:
            logger.warning("Raw Ollama output: %s", content)
            return _fallback_generate_content(prompt)

    async def generate_text(self, prompt: str, system: str = "") -> str:
        if "translate" in prompt.lower():
            if not await self._check_ollama():
                lang_match = re.search(r"into\s+(.+?)\.\n", prompt)
                target = lang_match.group(1).strip() if lang_match else "the target language"
                sep = prompt.find("\n\n")
                text = prompt[sep + 2:].strip() if sep != -1 else prompt
                return await _mymemory_translate(text, target)
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system or "You are a professional translator."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                }
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["message"]["content"].strip()
            except httpx.ConnectError:
                self._ollama_available = False
                lang_match = re.search(r"into\s+(.+?)\.\n", prompt)
                target = lang_match.group(1).strip() if lang_match else "the target language"
                sep = prompt.find("\n\n")
                text = prompt[sep + 2:].strip() if sep != -1 else prompt
                return await _mymemory_translate(text, target)
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Ollama HTTP error {e.response.status_code}: {e.response.text}")

        if not await self._check_ollama():
            return _fallback_generate_text(prompt)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"].strip()
        except httpx.ConnectError:
            self._ollama_available = False
            return _fallback_generate_text(prompt)
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama HTTP error {e.response.status_code}: {e.response.text}")

    async def generate_content(self, description: str) -> dict:
        prompt = f"Analyze this content description and generate social media posts:\n\n{description}"
        return await self.generate(prompt)

    async def translate(self, text: str, target_language: str) -> str:
        prompt = (
            f"Translate the ENTIRE following text into {target_language}.\n"
            f"CRITICAL: You MUST translate EVERY SINGLE WORD into {target_language}. "
            f"Do NOT leave any English words untranslated. Translate all sentences completely.\n"
            f"Keep the same line structure (newlines). Return ONLY the {target_language} translation:\n\n{text}"
        )
        return await self.generate_text(prompt)

    async def rewrite(self, text: str, tone: str, length: str) -> str:
        length_guide = {
            "short": "Rewrite in exactly 1-2 sentences (10-20 words). Be extremely concise.",
            "medium": "Rewrite in 3-4 sentences (30-50 words). Provide moderate detail.",
            "long": "Rewrite as a detailed paragraph of 5-7 sentences (70-100 words). Be thorough and descriptive.",
            "very long": "Rewrite as a multi-paragraph response with 8-12 sentences (120-180 words). Be very detailed and expansive.",
        }
        length_instruction = length_guide.get(length, length_guide["medium"])
        prompt = (
            f"Rewrite the following text with a '{tone}' tone.\n"
            f"LENGTH: {length}\n"
            f"LENGTH REQUIREMENT: {length_instruction}\n"
            f"IMPORTANT: You MUST strictly follow the length requirement above. Do NOT make it shorter or longer than specified.\n"
            f"Return ONLY the rewritten text, nothing else:\n\n{text}"
        )
        return await self.generate_text(prompt)


ai_provider = AIProvider()
